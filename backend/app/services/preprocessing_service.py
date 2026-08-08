"""
Data preprocessing pipeline.

Steps:
1. Load CSV
2. Drop rows with missing critical fields
3. Remove duplicate product names
4. Normalize text fields
5. Extract brand, parse price, infer skin types
6. Build search_text for embeddings
7. Persist to MongoDB
8. Generate embeddings and build FAISS index
"""

from datetime import UTC, datetime
from typing import Any

import pandas as pd
from bson import ObjectId

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.product_repository import ProductRepository
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.utils.price_utils import parse_price
from app.utils.ingredient_intel import analyse_ingredients
from app.utils.text_utils import (
    build_search_text,
    extract_brand,
    normalize_text,
    parse_ingredients,
)

logger = get_logger(__name__)


class PreprocessingService:
    """Orchestrates dataset ingestion into MongoDB + FAISS."""

    def __init__(
        self,
        product_repo: ProductRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._product_repo = product_repo
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    def load_and_clean(self, csv_path: str | None = None) -> pd.DataFrame:
        """Load CSV and apply cleaning transformations."""
        path = csv_path or str(settings.dataset_path)
        logger.info("Loading dataset from %s", path)
        df = pd.read_csv(path)

        initial_count = len(df)
        logger.info("Raw rows: %d", initial_count)

        # Drop rows missing critical fields
        df = df.dropna(subset=["product_name", "product_type"])
        df["product_name"] = df["product_name"].astype(str).str.strip()
        df["product_type"] = df["product_type"].astype(str).str.strip()
        df = df[df["product_name"] != ""]
        df = df[df["product_type"] != ""]

        # Remove duplicates by normalized product name
        df["_norm_name"] = df["product_name"].apply(normalize_text)
        df = df.drop_duplicates(subset=["_norm_name"], keep="first")
        df = df.drop(columns=["_norm_name"])

        logger.info(
            "After cleaning: %d rows (removed %d)",
            len(df),
            initial_count - len(df),
        )
        return df

    def transform_row(self, row: pd.Series) -> dict[str, Any]:
        """
        Turn one CSV row into a MongoDB document.

        Two changes from the original worth knowing:

        1. Everything derived now carries a CONFIDENCE. Brand and skin-type fit
           are guesses made from the product name and the ingredient list — the
           dataset contains neither. Storing the guess without its reliability
           is how a heuristic quietly becomes a claim in the UI.

        2. `search_text` now includes the concerns each active is commonly
           associated with. Previously the embedded text was name + type +
           brand + chemistry, so a query like "soothing for redness" could only
           match on how close those words happen to sit to ingredient names in
           general language. Folding in customer vocabulary gives the embedding
           something real to match against — the single biggest retrieval
           quality change in this re-ingest.
        """
        ingredients = parse_ingredients(row.get("clean_ingreds"))
        brand, brand_confidence = extract_brand(str(row["product_name"]))
        price, currency = parse_price(row.get("price"))
        product_type = normalize_text(str(row["product_type"])).title()

        analysis = analyse_ingredients(ingredients, product_type)
        active_names = [a["name"] for a in analysis["key_actives"]]

        search_text = build_search_text(
            str(row["product_name"]),
            product_type,
            brand,
            ingredients,
            concerns=analysis["concerns"],
            active_names=active_names,
        )
        now = datetime.now(UTC)
        return {
            "_id": ObjectId(),
            "product_name": str(row["product_name"]).strip(),
            "product_url": str(row.get("product_url", "")).strip(),
            "product_type": product_type,
            "brand": brand,
            "brand_confidence": brand_confidence,
            "ingredients": ingredients,
            "price": price,
            "price_currency": currency,
            "skin_types": analysis["skin_types"],
            "skin_type_confidence": analysis["skin_type_confidence"],
            "concerns": analysis["concerns"],
            "key_actives": analysis["key_actives"],
            "search_text": search_text,
            "faiss_index": None,
            "metadata": {
                "source": "skincare_products_clean.csv",
                "derived": ["brand", "skin_types", "concerns", "key_actives"],
                "ingredient_count": len(ingredients),
            },
            "created_at": now,
            "updated_at": now,
        }

    async def ingest(self, csv_path: str | None = None, *, reset: bool = True) -> dict[str, Any]:
        """
        Full ingestion pipeline: clean → MongoDB → embeddings → FAISS.

        Returns summary statistics.
        """
        df = self.load_and_clean(csv_path)
        documents = [self.transform_row(row) for _, row in df.iterrows()]

        if reset:
            deleted = await self._product_repo.delete_all()
            logger.info("Cleared %d existing products", deleted)

        inserted = await self._product_repo.insert_many(documents)
        logger.info("Inserted %d products into MongoDB", inserted)

        # Generate embeddings
        search_texts = [doc["search_text"] for doc in documents]
        embeddings = self._embedding_service.encode(search_texts)

        product_ids = [str(doc["_id"]) for doc in documents]
        self._vector_store.build(embeddings, product_ids)
        self._vector_store.save()

        # Update faiss_index on each document
        faiss_updates = [(pid, idx) for idx, pid in enumerate(product_ids)]
        await self._product_repo.update_faiss_indices(faiss_updates)

        return {
            "rows_processed": len(df),
            "products_inserted": inserted,
            "embeddings_generated": len(search_texts),
            "faiss_index_size": self._vector_store.size,
        }
