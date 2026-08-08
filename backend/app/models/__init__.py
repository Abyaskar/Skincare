"""MongoDB document models (internal persistence layer)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProductDocument(BaseModel):
    """Product stored in MongoDB after preprocessing."""

    id: str | None = Field(None, alias="_id")
    product_name: str
    product_url: str
    product_type: str
    brand: str
    ingredients: list[str]
    price: float | None = None
    price_currency: str = "GBP"
    skin_types: list[str] = Field(default_factory=list)
    skin_type_confidence: float = 0.0
    brand_confidence: float = 0.0
    concerns: list[str] = Field(default_factory=list)
    key_actives: list[dict[str, Any]] = Field(default_factory=list)
    search_text: str = ""
    faiss_index: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {"populate_by_name": True}


class FeedbackDocument(BaseModel):
    """User feedback on recommendations."""

    id: str | None = Field(None, alias="_id")
    product_id: str
    feedback_type: str
    request_id: str | None = None
    rank: int | None = None
    strategy: str | None = None
    reason_code: str | None = None
    surface: str | None = None
    rating: int | None = None
    comment: str | None = None
    session_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    model_config = {"populate_by_name": True}


class ChatHistoryDocument(BaseModel):
    """Persisted RAG chat turns."""

    id: str | None = Field(None, alias="_id")
    session_id: str
    user_message: str
    assistant_response: str
    retrieved_product_ids: list[str] = Field(default_factory=list)
    model: str
    created_at: datetime = Field(default_factory=utc_now)

    model_config = {"populate_by_name": True}
