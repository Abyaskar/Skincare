"""Feedback and search schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse


class FeedbackType(str, Enum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    IRRELEVANT = "irrelevant"
    PURCHASED = "purchased"


class ReasonCode(str, Enum):
    """
    Why a recommendation missed.

    This is the difference between feedback as sentiment and feedback as
    engineering signal. "Too expensive" is a merchandising input;
    "contains something I avoid" is a filter bug alert that should page
    someone; "wrong product type" is a ranking bug. Same single tap.
    """

    TOO_EXPENSIVE = "too_expensive"
    WRONG_PRODUCT_TYPE = "wrong_product_type"
    CONTAINS_AVOIDED = "contains_avoided"
    WRONG_SKIN_TYPE = "wrong_skin_type"
    ALREADY_OWN = "already_own"
    NOT_INTERESTED = "not_interested"


class FeedbackRequest(BaseModel):
    """POST /feedback body."""

    product_id: str
    feedback_type: FeedbackType
    request_id: str | None = Field(
        None,
        description="Links this feedback to the recommendation that produced it",
    )
    rank: int | None = Field(None, ge=1, description="Position in the result set")
    strategy: str | None = None
    reason_code: ReasonCode | None = None
    surface: str | None = Field(None, description="recommendation | search | chat | similar")
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)
    session_id: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    product_id: str
    feedback_type: FeedbackType
    request_id: str | None = None
    reason_code: ReasonCode | None = None
    rating: int | None = None
    comment: str | None = None
    created_at: datetime


class SearchRequest(BaseModel):
    """POST /search body — semantic product search."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(10, ge=1, le=50)
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)
    brands: list[str] = Field(default_factory=list)
    product_types: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    request_id: str
    query: str
    total: int
    products: list[ProductResponse]
    low_confidence: bool = False
    low_confidence_reason: str | None = None
    top_similarity: float | None = None
    took_ms: int = 0
