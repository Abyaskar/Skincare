"""Feedback repository — persists user feedback on recommendations."""

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger
from app.models import FeedbackDocument

logger = get_logger(__name__)


class FeedbackRepository:
    """Async feedback data access."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[settings.feedback_collection]

    @staticmethod
    def _serialize(doc: dict[str, Any]) -> FeedbackDocument:
        doc["_id"] = str(doc["_id"])
        return FeedbackDocument.model_validate(doc)

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("product_id")
        await self._collection.create_index("created_at")
        await self._collection.create_index("request_id")
        await self._collection.create_index("reason_code")

    async def create(self, data: dict[str, Any]) -> FeedbackDocument:
        try:
            result = await self._collection.insert_one(data)
            doc = await self._collection.find_one({"_id": result.inserted_id})
            return self._serialize(doc)  # type: ignore[arg-type]
        except Exception as exc:
            logger.exception("Feedback insert failed")
            raise DatabaseError("Failed to save feedback", details={"error": str(exc)}) from exc

    async def find_by_product(self, product_id: str, limit: int = 50) -> list[FeedbackDocument]:
        cursor = (
            self._collection.find({"product_id": product_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(doc) async for doc in cursor]
