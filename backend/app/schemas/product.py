"""
Product-related API schemas.

The response now carries everything the UI needs to EXPLAIN a result, not just
display it. `MatchReason` items are generated from the filters that actually
ran — they are facts about what the system did, not sentences a model wrote.
That is what lets the "Why this?" panel work with the LLM switched off.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SkinType(str, Enum):
    OILY = "oily"
    DRY = "dry"
    COMBINATION = "combination"
    SENSITIVE = "sensitive"
    NORMAL = "normal"
    ALL = "all"


class RecommendationStrategy(str, Enum):
    CONTENT = "content"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class MatchReason(BaseModel):
    """
    One checkable fact about why a product is in the result set.

    `kind` drives the icon: pass (green tick), caution (amber), info (neutral).
    Every reason is derived from an applied filter or a product field, so it is
    auditable — the customer can verify it against the label.
    """

    kind: str = Field(description="pass | caution | info")
    label: str = Field(description="Short human-readable fact")
    detail: str | None = Field(None, description="Optional supporting detail")


class ProductResponse(BaseModel):
    """Single product returned by the API."""

    id: str
    product_name: str
    product_url: str
    product_type: str
    brand: str
    brand_confidence: float = 0.0
    ingredients: list[str]
    price: float | None = None
    price_currency: str = "GBP"
    skin_types: list[str] = Field(default_factory=list)
    skin_type_confidence: float = 0.0
    concerns: list[str] = Field(default_factory=list)
    key_actives: list[dict[str, Any]] = Field(default_factory=list)
    search_text: str = ""
    created_at: datetime | None = None

    # --- ranking / explanation ---
    score: float | None = Field(None, description="Blended ranking score, not a confidence")
    similarity: float | None = Field(None, description="Raw cosine similarity — thresholdable")
    match_strength: str | None = Field(None, description="strong | moderate | weak")
    match_reasons: list[MatchReason] = Field(default_factory=list)
    rank: int | None = None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


class ProductDetailResponse(ProductResponse):
    metadata: dict[str, Any] = Field(default_factory=dict)


class FacetsResponse(BaseModel):
    """
    GET /facets — everything the guided flow needs to build its own controls.

    Without this the frontend would hardcode brand lists and price ranges,
    which silently rot the moment the catalogue changes.
    """

    brands: list[str]
    product_types: list[str]
    price_min: float
    price_max: float
    avoid_groups: list[str]
    concerns: list[str]
    total_products: int
    products_with_known_price: int
