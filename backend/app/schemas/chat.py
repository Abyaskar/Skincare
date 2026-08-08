"""RAG chat request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse


class ChatRequest(BaseModel):
    """POST /chat body — natural language beauty Q&A."""

    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(
        None,
        description="Optional session ID to group conversation history",
    )
    top_k: int = Field(5, ge=1, le=20, description="Products retrieved for RAG context")


class ChatResponse(BaseModel):
    """RAG-generated answer with cited products."""

    session_id: str
    message: str
    answer: str
    retrieved_products: list[ProductResponse]
    model: str
    created_at: datetime
    safety_redirect: str | None = None
    low_confidence: bool = False
    top_similarity: float | None = None
    claims_removed: int = 0


class HistoryItem(BaseModel):
    """Single chat history record."""

    id: str
    session_id: str
    user_message: str
    assistant_response: str
    retrieved_product_ids: list[str]
    model: str
    created_at: datetime


class HistoryResponse(BaseModel):
    """GET /history response."""

    items: list[HistoryItem]
    total: int
