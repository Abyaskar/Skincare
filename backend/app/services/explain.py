"""
Explanation builder.

WHY THIS IS A SEPARATE MODULE
-----------------------------
"Why was this recommended?" is the most important screen in the product, so
its content must not depend on a language model being available, in a good
mood, or affordable this month.

Every fact produced here is derived from (a) the filters the customer actually
set and (b) fields on the product document. Nothing is generated. That gives
three properties we need:

  * AUDITABLE  — each line can be checked against the product label
  * AVAILABLE  — works when the LLM is down (the L1 degradation level)
  * SAFE       — describes MATCHING, never OUTCOMES. "Contains salicylic acid,
                 commonly used in products aimed at breakout-prone skin" is a
                 statement about the formula. "Clears acne" is a medical claim
                 and would reclassify a cosmetic. We never generate the second.

The LLM's only job downstream is to add one softened sentence. If it fails,
the panel still renders completely.
"""

from __future__ import annotations

from app.core.config import settings
from app.models import ProductDocument
from app.schemas.product import MatchReason
from app.schemas.recommendation import RecommendationFilters
from app.utils.ingredient_intel import find_matching_ingredients, resolve_avoid_terms
from app.utils.price_utils import format_price


def match_strength(similarity: float | None) -> str | None:
    """
    Turn a raw cosine similarity into three words a customer can read.

    We never expose the float. 0.71 means nothing to a shopper, and because the
    hybrid score is max-normalised it isn't comparable across queries anyway.
    Three buckets are honest; a decimal is false precision.
    """
    if similarity is None:
        return None
    if similarity >= settings.strong_match_threshold:
        return "strong"
    if similarity >= settings.relevance_floor:
        return "moderate"
    return "weak"


def build_match_reasons(
    doc: ProductDocument,
    filters: RecommendationFilters,
    similarity: float | None = None,
) -> list[MatchReason]:
    """Assemble the checkable facts behind one result."""
    reasons: list[MatchReason] = []

    # --- Budget: a hard filter, so this is a fact, not an opinion -----------
    if doc.price is None:
        reasons.append(
            MatchReason(
                kind="caution",
                label="Price unavailable",
                detail="We couldn't read a price for this product, so we can't check it against your budget.",
            )
        )
    elif filters.max_price is not None:
        reasons.append(
            MatchReason(
                kind="pass",
                label=f"{format_price(doc.price, doc.price_currency)} — within your budget",
                detail=f"Your limit was {format_price(filters.max_price, doc.price_currency)}.",
            )
        )

    # --- Avoidance: the highest-stakes line in the whole UI -----------------
    for term in filters.ingredients_exclude:
        label, patterns = resolve_avoid_terms(term)
        if not patterns:
            continue
        hits = find_matching_ingredients(doc.ingredients, patterns)
        if hits:
            # Should not happen — the filter runs first — but if it ever does,
            # the customer must see it rather than a false green tick.
            reasons.append(
                MatchReason(
                    kind="caution",
                    label=f"Contains {label}",
                    detail=", ".join(hits[:4]),
                )
            )
        elif doc.ingredients:
            reasons.append(
                MatchReason(
                    kind="pass",
                    label=f"No {label} found in the ingredient list",
                    detail="Matched against the ingredient names published for this product.",
                )
            )
        else:
            # No ingredient data means we cannot make the claim. Showing an
            # unearned green tick on an allergy check is the worst single thing
            # this product could do, so we say nothing rather than reassure.
            reasons.append(
                MatchReason(
                    kind="caution",
                    label=f"Can't check for {label}",
                    detail="No ingredient list is published for this product.",
                )
            )

    # --- Requested ingredients ---------------------------------------------
    if filters.ingredients_include:
        found = []
        for term in filters.ingredients_include:
            _, patterns = resolve_avoid_terms(term)
            if find_matching_ingredients(doc.ingredients, patterns):
                found.append(term)
        if found:
            reasons.append(
                MatchReason(
                    kind="pass",
                    label=f"Contains {', '.join(found)}",
                    detail="You asked for this.",
                )
            )

    # --- Skin type: inferred, so it is always marked as inferred ------------
    if filters.skin_type and filters.skin_type.value in doc.skin_types:
        if doc.skin_type_confidence >= 0.7:
            reasons.append(
                MatchReason(
                    kind="info",
                    label=f"Often suited to {filters.skin_type.value} skin",
                    detail="Based on the ingredients in this product, not a claim from the brand.",
                )
            )
        else:
            reasons.append(
                MatchReason(
                    kind="caution",
                    label=f"May suit {filters.skin_type.value} skin",
                    detail="We inferred this from one ingredient, so treat it as a weak signal.",
                )
            )

    # --- What the formula is built around ----------------------------------
    for active in doc.key_actives[:2]:
        reasons.append(
            MatchReason(
                kind="info",
                label=f"Contains {active.get('name', '')}",
                detail=active.get("blurb"),
            )
        )

    # --- How the text matched ----------------------------------------------
    strength = match_strength(similarity)
    if strength == "strong":
        reasons.append(
            MatchReason(
                kind="info",
                label="Closely matched what you described",
                detail="Your wording sits close to this product's profile.",
            )
        )
    elif strength == "weak":
        reasons.append(
            MatchReason(
                kind="caution",
                label="Loosely matched what you described",
                detail="We're showing this because your filters narrowed the field, not because it's a close match.",
            )
        )

    return reasons
