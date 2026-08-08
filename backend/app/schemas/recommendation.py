"""Recommendation request/response schemas."""

from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse, RecommendationStrategy, SkinType


class RecommendationFilters(BaseModel):
    """
    Hard constraints. These are applied deterministically in MongoDB and again
    as a post-filter — never by the model, never as a ranking preference.

    `ingredients_exclude` accepts customer-facing words ("fragrance") as well as
    raw INCI names. It is expanded through ingredient_intel into the full set of
    names that satisfy the rule, so "fragrance" also catches parfum, linalool,
    limonene and the rest. Exact-string matching would have caught none of them.
    """

    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)
    skin_type: SkinType | None = None
    ingredients_include: list[str] = Field(default_factory=list)
    ingredients_exclude: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    product_types: list[str] = Field(default_factory=list)


class RelaxSuggestion(BaseModel):
    """
    One-tap way out of an over-constrained search.

    `result_count` is computed BEFORE the customer commits, so the button can
    say "+7 matches" instead of asking them to guess.
    """

    filter_name: str
    label: str
    result_count: int


class RecommendRequest(BaseModel):
    """POST /recommend body."""

    query: str | None = Field(
        None,
        description="Natural-language intent for semantic/hybrid modes",
        examples=["hydrating moisturiser for dry sensitive skin, no fragrance"],
    )
    product_id: str | None = Field(None, description="Seed product for 'more like this'")
    strategy: RecommendationStrategy = RecommendationStrategy.HYBRID
    top_k: int = Field(10, ge=1, le=50)
    filters: RecommendationFilters = Field(default_factory=RecommendationFilters)
    diversify: bool = Field(
        True,
        description="Cap results per brand so one brand can't fill the shortlist",
    )


class RecommendResponse(BaseModel):
    """
    Recommendation results with the honesty fields attached.

    `request_id` is the most important field here. It threads impression -> click
    -> feedback -> cart, and without it recommendation acceptance rate is not
    computable at all.
    """

    request_id: str
    strategy: RecommendationStrategy
    query: str | None = None
    seed_product_id: str | None = None
    total: int
    products: list[ProductResponse]
    filters_applied: RecommendationFilters

    # --- honesty layer ---
    low_confidence: bool = False
    low_confidence_reason: str | None = None
    top_similarity: float | None = None
    candidates_before_filters: int = 0
    filter_attrition: dict[str, int] = Field(
        default_factory=dict,
        description="How many candidates each filter removed — answers 'why only 2 results?'",
    )
    relax_suggestions: list[RelaxSuggestion] = Field(default_factory=list)
    took_ms: int = 0
