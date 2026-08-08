"""
Semantic search service.

Search exists to kill the zero-result page. Customers describe symptoms
("tight after washing", "shiny by lunchtime") and products are named after
ingredients — keyword search sits helplessly between those two languages.

The relevance floor matters even more here than on /recommend: a
nearest-neighbour index has no concept of "nothing is close", so without a
floor the query "iphone charger" returns ten moisturisers with a straight face.
"""

import time
import uuid

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger
from app.repositories.product_repository import ProductRepository
from app.schemas.feedback import SearchRequest, SearchResponse
from app.schemas.product import ProductResponse
from app.schemas.recommendation import RecommendationFilters
from app.services.embedding_service import EmbeddingService
from app.services.recommendation_service import doc_to_response
from app.services.vector_store import VectorStore

logger = get_logger(__name__)


class SearchService:
    """Semantic product search over the FAISS index."""

    def __init__(
        self,
        product_repo: ProductRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._product_repo = product_repo
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    async def search(self, request: SearchRequest) -> SearchResponse:
        started = time.perf_counter()
        request_id = str(uuid.uuid4())

        if not self._vector_store.is_loaded:
            raise VectorStoreError("Vector index not loaded. Run ingestion first.")

        embedding = await self._embedding_service.encode_single_async(request.query)
        raw = self._vector_store.search(embedding, top_k=min(request.top_k * 8, 300))

        top_similarity = raw[0][1] if raw else None

        docs = await self._product_repo.find_by_ids([pid for pid, _ in raw])
        doc_map = {d.id: d for d in docs if d.id}
        score_map = dict(raw)

        # Search filters are a lighter-touch subset of the recommend filters:
        # this surface is for browsing intent, not personal fit. The UI bridges
        # into the guided flow when the customer wants their skin considered.
        filters = RecommendationFilters(
            min_price=request.min_price,
            max_price=request.max_price,
            brands=request.brands,
            product_types=request.product_types,
        )

        results: list[ProductResponse] = []
        for pid, _ in raw:
            doc = doc_map.get(pid)
            if not doc:
                continue
            sim = score_map.get(pid)
            if request.min_price is not None and (doc.price is None or doc.price < request.min_price):
                continue
            if request.max_price is not None and (doc.price is None or doc.price > request.max_price):
                continue
            if request.brands and not any(b.lower() in doc.brand.lower() for b in request.brands):
                continue
            if request.product_types and not any(
                t.lower() in doc.product_type.lower() for t in request.product_types
            ):
                continue
            results.append(
                doc_to_response(
                    doc,
                    score=sim,
                    similarity=sim,
                    filters=filters,
                    rank=len(results) + 1,
                )
            )
            if len(results) >= request.top_k:
                break

        low_confidence = False
        reason: str | None = None
        if not results:
            low_confidence, reason = True, "no_results"
        elif top_similarity is not None and top_similarity < settings.relevance_floor:
            low_confidence, reason = True, "below_relevance_floor"

        took_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "search request_id=%s q=%r results=%d low_confidence=%s took_ms=%d",
            request_id, request.query, len(results), low_confidence, took_ms,
        )

        return SearchResponse(
            request_id=request_id,
            query=request.query,
            total=len(results),
            products=results,
            low_confidence=low_confidence,
            low_confidence_reason=reason,
            top_similarity=top_similarity,
            took_ms=took_ms,
        )
