"""
Product repository — all async MongoDB CRUD for the products collection.

Repositories contain zero business logic; they only translate between
MongoDB documents and domain models.
"""

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.exceptions import DatabaseError, NotFoundError
from app.core.logging import get_logger
from app.models import ProductDocument, utc_now

logger = get_logger(__name__)


class ProductRepository:
    """Async product data access."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[settings.products_collection]

    @staticmethod
    def _serialize(doc: dict[str, Any]) -> ProductDocument:
        doc["_id"] = str(doc["_id"])
        return ProductDocument.model_validate(doc)

    async def ensure_indexes(self) -> None:
        """Create indexes for filter queries."""
        await self._collection.create_index("product_name")
        await self._collection.create_index("brand")
        await self._collection.create_index("product_type")
        await self._collection.create_index("price")
        await self._collection.create_index("faiss_index")

    async def insert_many(self, products: list[dict[str, Any]]) -> int:
        if not products:
            return 0
        try:
            result = await self._collection.insert_many(products)
            return len(result.inserted_ids)
        except Exception as exc:
            logger.exception("Bulk insert failed")
            raise DatabaseError("Failed to insert products", details={"error": str(exc)}) from exc

    async def delete_all(self) -> int:
        result = await self._collection.delete_many({})
        return result.deleted_count

    async def count(self, query: dict[str, Any] | None = None) -> int:
        return await self._collection.count_documents(query or {})

    async def find_by_id(self, product_id: str) -> ProductDocument:
        try:
            oid = ObjectId(product_id)
        except Exception as exc:
            raise NotFoundError(f"Invalid product ID: {product_id}") from exc

        doc = await self._collection.find_one({"_id": oid})
        if not doc:
            raise NotFoundError(f"Product not found: {product_id}")
        return self._serialize(doc)

    async def find_by_ids(self, product_ids: list[str]) -> list[ProductDocument]:
        oids = []
        for pid in product_ids:
            try:
                oids.append(ObjectId(pid))
            except Exception:
                continue
        if not oids:
            return []
        cursor = self._collection.find({"_id": {"$in": oids}})
        return [self._serialize(doc) async for doc in cursor]

    async def find_by_faiss_indices(self, indices: list[int]) -> list[ProductDocument]:
        cursor = self._collection.find({"faiss_index": {"$in": indices}})
        docs = [self._serialize(doc) async for doc in cursor]
        index_map = {d.faiss_index: d for d in docs if d.faiss_index is not None}
        return [index_map[i] for i in indices if i in index_map]

    async def list_products(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        brand: str | None = None,
        product_type: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        sort: str = "name",
    ) -> tuple[list[ProductDocument], int]:
        query: dict[str, Any] = {}
        if brand:
            query["brand"] = {"$regex": brand, "$options": "i"}
        if product_type:
            query["product_type"] = {"$regex": product_type, "$options": "i"}
        if min_price is not None or max_price is not None:
            price_q: dict[str, float] = {}
            if min_price is not None:
                price_q["$gte"] = min_price
            if max_price is not None:
                price_q["$lte"] = max_price
            query["price"] = price_q

        # Alphabetical sorting is not neutral — it silently merchandises the
        # 'A' brands onto page one of every category. Offer real alternatives.
        sort_spec = {
            "name": ("product_name", 1),
            "price_asc": ("price", 1),
            "price_desc": ("price", -1),
        }.get(sort, ("product_name", 1))
        if sort in ("price_asc", "price_desc"):
            # Unknown prices are excluded from price sorts rather than
            # appearing as the cheapest thing in the catalogue.
            query["price"] = {**query.get("price", {}), "$ne": None}
            total = await self.count(query)
        else:
            total = await self.count(query)
        skip = (page - 1) * page_size
        cursor = (
            self._collection.find(query)
            .sort(*sort_spec)
            .skip(skip)
            .limit(page_size)
        )
        items = [self._serialize(doc) async for doc in cursor]
        return items, total

    async def find_with_filters(self, mongo_filter: dict[str, Any]) -> list[ProductDocument]:
        cursor = self._collection.find(mongo_filter)
        return [self._serialize(doc) async for doc in cursor]

    async def update_faiss_indices(self, updates: list[tuple[str, int]]) -> None:
        """Batch update faiss_index after vector index build."""
        from pymongo import UpdateOne

        ops = [
            UpdateOne(
                {"_id": ObjectId(pid)},
                {"$set": {"faiss_index": idx, "updated_at": utc_now()}},
            )
            for pid, idx in updates
        ]
        if ops:
            await self._collection.bulk_write(ops)

    async def get_all_search_texts(self) -> list[tuple[str, str, int | None]]:
        """Return (product_id, search_text, faiss_index) for all products."""
        cursor = self._collection.find({}, {"search_text": 1, "faiss_index": 1})
        results = []
        async for doc in cursor:
            results.append((str(doc["_id"]), doc.get("search_text", ""), doc.get("faiss_index")))
        return results


    async def get_facets(self) -> dict:
        """
        Aggregate the real filter options out of the catalogue.

        Computed from the data rather than hardcoded in the frontend, so the
        UI can never offer a filter that returns nothing.
        """
        pipeline_brands = [
            {"$group": {"_id": "$brand", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": 2}}},
            {"$sort": {"n": -1}},
            {"$limit": 120},
        ]
        brands = [
            d["_id"] async for d in self._collection.aggregate(pipeline_brands) if d["_id"]
        ]

        types = await self._collection.distinct("product_type")
        concerns = await self._collection.distinct("concerns")

        price_stats = await self._collection.aggregate([
            {"$match": {"price": {"$ne": None}}},
            {"$group": {
                "_id": None,
                "min": {"$min": "$price"},
                "max": {"$max": "$price"},
                "n": {"$sum": 1},
            }},
        ]).to_list(1)
        stats = price_stats[0] if price_stats else {}

        return {
            "brands": sorted(brands),
            "product_types": sorted(t for t in types if t),
            "concerns": sorted(c for c in concerns if c),
            "price_min": float(stats.get("min") or 0.0),
            "price_max": float(stats.get("max") or 0.0),
            "total": await self.count(),
            "with_price": int(stats.get("n") or 0),
        }
