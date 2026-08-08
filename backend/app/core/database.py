"""
Async MongoDB connection manager using Motor.

A single client is created at startup and injected into repositories
via FastAPI dependency injection.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger

logger = get_logger(__name__)


class MongoDB:
    """Lifecycle-managed MongoDB client wrapper."""

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    @classmethod
    async def connect(cls) -> None:
        """Establish connection pool at application startup."""
        try:
            cls.client = AsyncIOMotorClient(settings.mongodb_uri)
            cls.db = cls.client[settings.mongodb_db_name]
            await cls.client.admin.command("ping")
            logger.info("Connected to MongoDB: %s", settings.mongodb_db_name)
        except Exception as exc:
            logger.exception("MongoDB connection failed")
            raise DatabaseError("Failed to connect to MongoDB", details={"error": str(exc)}) from exc

    @classmethod
    async def disconnect(cls) -> None:
        """Close connection pool at shutdown."""
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed")

    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        if cls.db is None:
            raise DatabaseError("MongoDB is not connected")
        return cls.db


def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency — returns active database handle."""
    return MongoDB.get_database()
