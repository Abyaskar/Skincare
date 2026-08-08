"""Chat history repository — persists RAG conversation turns."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger
from app.models import ChatHistoryDocument

logger = get_logger(__name__)


class HistoryRepository:
    """Async chat history data access."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[settings.history_collection]

    @staticmethod
    def _serialize(doc: dict[str, Any]) -> ChatHistoryDocument:
        doc["_id"] = str(doc["_id"])
        return ChatHistoryDocument.model_validate(doc)

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("session_id")
        await self._collection.create_index("created_at")

    async def create(self, data: dict[str, Any]) -> ChatHistoryDocument:
        try:
            result = await self._collection.insert_one(data)
            doc = await self._collection.find_one({"_id": result.inserted_id})
            return self._serialize(doc)  # type: ignore[arg-type]
        except Exception as exc:
            logger.exception("History insert failed")
            raise DatabaseError("Failed to save chat history", details={"error": str(exc)}) from exc

    async def list_history(
        self,
        *,
        session_id: str | None = None,
        limit: int = 50,
    ) -> tuple[list[ChatHistoryDocument], int]:
        query: dict[str, Any] = {}
        if session_id:
            query["session_id"] = session_id
        total = await self._collection.count_documents(query)
        cursor = (
            self._collection.find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        items = [self._serialize(doc) async for doc in cursor]
        return items, total


    async def delete_by_session(self, session_id: str) -> int:
        """Real deletion behind the UI's "Clear history" control.

        Chat history holds free-text skin concerns. A delete control that
        only hides rows is worse than no control at all.
        """
        result = await self._collection.delete_many({"session_id": session_id})
        return result.deleted_count
