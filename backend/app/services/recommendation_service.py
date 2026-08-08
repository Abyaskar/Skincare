"""
Recommendation service — content-based, semantic, and hybrid.

THE ARCHITECTURAL RULE THIS FILE ENFORCES
------------------------------------------
    Hard constraints are decided by rules. Relevance is decided by vectors.
    Neither is decided by a language model.

A retailer evaluating this system asks one question that decides the deal:
"can your AI recommend a product containing an ingredient the customer told you
they're allergic to?" The only acceptable answer is no — because the exclusion
is a database filter applied before ranking, and the model never sees the
candidates it removed.

WHAT CHANGED FROM THE ORIGINAL
------------------------------
1. RELEVANCE FLOOR. FAISS returns nearest neighbours regardless of distance, so
   the old service could never say "I don't have a good match" — it would
   happily return ten skincare products for the query "iphone charger".
2. SYNONYM-AWARE EXCLUSIONS. The old filter was exact-string, so excluding
   "fragrance" caught nothing: the catalogue calls it `parfum`, its 3rd most
   common ingredient. For an allergy feature, partial coverage is worse than
   none, because it is trusted.
3. FILTER ATTRITION TRACKING. We record how many candidates each filter
   removed, so the UI can answer "why did I only get two results?" and offer
   the specific relax option that would help.
4. DIVERSITY CAP. The old content scorer gave same-brand products a permanent
   +0.1 bonus — a filter bubble hiding in a utility function. Removed, and
   replaced with an explicit per-brand cap on the final result set.
5. NULLABLE PRICE. Unknown prices no longer pass budget filters as "free".
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from app.core.config import settings
from app.core.exceptions import ValidationError, VectorStoreError
from app.core.logging import get_logger
from app.models import ProductDocument
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductResponse, RecommendationStrategy, SkinType
from app.schemas.recommendation import (
    RecommendationFilters,
    RecommendRequest,
    RecommendResponse,
    RelaxSuggestion,
)
from app.services.embedding_service import EmbeddingService
from app.services.explain import build_match_reasons, match_strength
from app.services.vector_store import VectorStore
from app.utils.ingredient_intel import (
    find_matching_ingredients,
    product_violates,
    resolve_avoid_terms,
)

logger = get_logger(__name__)


def _escape(pattern: str) -> str:
    """Escape regex metacharacters in ingredient names (e.g. 'dr. jart+')."""
    return re.escape(pattern)


def doc_to_response(
    doc: ProductDocument,
    *,
    score: float | None = None,
    similarity: float | None = None,
    filters: RecommendationFilters | None = None,
    rank: int | None = None,
) -> ProductResponse:
    """Convert a stored document into an API product, with its explanation."""
    return ProductResponse(
        id=doc.id or "",
        product_name=doc.product_name,
        product_url=doc.product_url,
        product_type=doc.product_type,
        brand=doc.brand,
        brand_confidence=doc.brand_confidence,
        ingredients=doc.ingredients,
        price=doc.price,
        price_currency=doc.price_currency,
        skin_types=doc.skin_types,
        skin_type_confidence=doc.skin_type_confidence,
        concerns=doc.concerns,
        key_actives=doc.key_actives,
        search_text=doc.search_text,
        created_at=doc.created_at,
        score=score,
        similarity=similarity,
        match_strength=match_strength(similarity),
        match_reasons=build_match_reasons(doc, filters, similarity) if filters else [],
        rank=rank,
    )


class RecommendationService:
    """Multi-strategy product recommendation engine."""

    def __init__(
        self,
        product_repo: ProductRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._product_repo = product_repo
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    # ------------------------------------------------------------------
    # Deterministic filtering — the safety layer
    # ------------------------------------------------------------------

    def _build_mongo_filter(self, filters: RecommendationFilters) -> dict[str, Any]:
        """
        Translate customer constraints into a MongoDB query.

        Ingredient rules use regex rather than exact array membership so that
        "fragrance" expands to parfum|linalool|limonene|... . MongoDB applies a
        regex to every element of an array field, which is the semantics we need.
        """
        conditions: list[dict[str, Any]] = []

        if filters.min_price is not None or filters.max_price is not None:
            price_q: dict[str, Any] = {}
            if filters.min_price is not None:
                price_q["$gte"] = filters.min_price
            if filters.max_price is not None:
                price_q["$lte"] = filters.max_price
            # A null price is "unknown", not "cheap" — it cannot satisfy a budget.
            price_q["$ne"] = None
            conditions.append({"price": price_q})

        if filters.skin_type and filters.skin_type != SkinType.ALL:
            conditions.append({"skin_types": filters.skin_type.value})

        if filters.brands:
            conditions.append(
                {"$or": [{"brand": {"$regex": _escape(b), "$options": "i"}} for b in filters.brands]}
            )

        if filters.product_types:
            conditions.append(
                {
                    "$or": [
                        {"product_type": {"$regex": _escape(t), "$options": "i"}}
                        for t in filters.product_types
                    ]
                }
            )

        for term in filters.ingredients_include:
            _, patterns = resolve_avoid_terms(term)
            if patterns:
                rx = "|".join(_escape(p) for p in patterns)
                conditions.append({"ingredients": {"$regex": rx, "$options": "i"}})

        for term in filters.ingredients_exclude:
            _, patterns = resolve_avoid_terms(term)
            if patterns:
                rx = "|".join(_escape(p) for p in patterns)
                conditions.append(
                    {"ingredients": {"$not": {"$regex": rx, "$options": "i"}}}
                )

        if not conditions:
            return {}
        return conditions[0] if len(conditions) == 1 else {"$and": conditions}

    def _check(self, doc: ProductDocument, filters: RecommendationFilters) -> str | None:
        """
        Re-apply every constraint in Python. Returns the name of the first
        filter this product fails, or None if it passes.

        Running the checks twice is deliberate. The Mongo query narrows the
        candidate set; this pass guarantees nothing slipped through a
        query-construction mistake into a customer's results. On an allergy
        rule, belt and braces is the correct engineering posture.
        """
        if filters.max_price is not None and (doc.price is None or doc.price > filters.max_price):
            return "max_price"
        if filters.min_price is not None and (doc.price is None or doc.price < filters.min_price):
            return "min_price"
        if filters.skin_type and filters.skin_type != SkinType.ALL:
            if filters.skin_type.value not in doc.skin_types:
                return "skin_type"
        if filters.brands and not any(b.lower() in doc.brand.lower() for b in filters.brands):
            return "brands"
        if filters.product_types and not any(
            t.lower() in doc.product_type.lower() for t in filters.product_types
        ):
            return "product_types"
        if filters.ingredients_exclude and product_violates(
            doc.ingredients, filters.ingredients_exclude
        ):
            return "ingredients_exclude"
        for term in filters.ingredients_include:
            _, patterns = resolve_avoid_terms(term)
            if patterns and not find_matching_ingredients(doc.ingredients, patterns):
                return "ingredients_include"
        return None

    def _filter_with_attrition(
        self,
        candidates: list[tuple[ProductDocument, float]],
        filters: RecommendationFilters,
    ) -> tuple[list[tuple[ProductDocument, float]], dict[str, int]]:
        """Filter, and record which constraint removed how many candidates."""
        kept: list[tuple[ProductDocument, float]] = []
        attrition: dict[str, int] = {}
        for doc, score in candidates:
            failed = self._check(doc, filters)
            if failed:
                attrition[failed] = attrition.get(failed, 0) + 1
            else:
                kept.append((doc, score))
        return kept, attrition

    @staticmethod
    def _diversify(
        results: list[tuple[ProductDocument, float]],
        top_k: int,
        max_per_brand: int,
    ) -> list[tuple[ProductDocument, float]]:
        """
        Cap how much of the shortlist one brand can occupy.

        Applied after ranking, so it never promotes a worse product above a
        better one — it only stops the fifth product from the same brand from
        crowding out an option the customer has never seen.
        """
        selected: list[tuple[ProductDocument, float]] = []
        overflow: list[tuple[ProductDocument, float]] = []
        counts: dict[str, int] = {}
        for doc, score in results:
            key = doc.brand.lower()
            if counts.get(key, 0) >= max_per_brand:
                overflow.append((doc, score))
                continue
            counts[key] = counts.get(key, 0) + 1
            selected.append((doc, score))
            if len(selected) >= top_k:
                return selected
        # If diversity starved the list, refill rather than return fewer
        # results than we actually have.
        selected.extend(overflow[: max(0, top_k - len(selected))])
        return selected

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    async def _content_based(
        self,
        product_id: str,
        top_k: int,
        filters: RecommendationFilters,
    ) -> tuple[list[tuple[ProductDocument, float]], dict[str, int], int]:
        """
        "More like this" — ingredient overlap with a seed product.

        Weighted Jaccard: rare shared ingredients count more than common ones.
        Sharing `retinol` should mean far more than sharing `water`, and plain
        Jaccard treats them identically — which is why two unrelated products
        with thirty shared fillers used to score as similar.
        """
        seed = await self._product_repo.find_by_id(product_id)
        seed_ings = set(seed.ingredients)

        mongo_filter = self._build_mongo_filter(filters)
        candidates = await self._product_repo.find_with_filters(mongo_filter)
        candidates = [c for c in candidates if c.id != seed.id]
        total_candidates = len(candidates)

        df: dict[str, int] = {}
        for doc in candidates:
            for ing in set(doc.ingredients):
                df[ing] = df.get(ing, 0) + 1
        n = max(1, len(candidates))

        def weight(ing: str) -> float:
            return 1.0 / (1.0 + (df.get(ing, 0) / n) * 10.0)

        scored: list[tuple[ProductDocument, float]] = []
        for doc in candidates:
            doc_ings = set(doc.ingredients)
            union = seed_ings | doc_ings
            if not union:
                continue
            shared = seed_ings & doc_ings
            num = sum(weight(i) for i in shared)
            den = sum(weight(i) for i in union)
            jaccard = num / den if den else 0.0
            type_bonus = 0.15 if doc.product_type == seed.product_type else 0.0
            # NOTE: the same-brand bonus that used to live here was removed.
            # It quietly biased every "similar products" rail toward the brand
            # the customer was already looking at.
            score = jaccard + type_bonus
            if score > 0:
                scored.append((doc, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k], {}, total_candidates

    async def _semantic(
        self,
        query: str,
        top_k: int,
        filters: RecommendationFilters,
        exclude_id: str | None = None,
    ) -> tuple[list[tuple[ProductDocument, float]], dict[str, int], int, float | None]:
        """Vector similarity search, then deterministic filtering."""
        if not self._vector_store.is_loaded:
            raise VectorStoreError("Vector index not loaded. Run ingestion first.")

        embedding = await self._embedding_service.encode_single_async(query)

        # Over-fetch, because filtering happens after retrieval. The multiplier
        # scales with how many constraints are set — the more the customer has
        # narrowed, the deeper we must look to still find top_k survivors. A
        # fixed 5x was the cause of silent "filter starvation".
        constraint_count = sum(
            [
                filters.max_price is not None,
                filters.min_price is not None,
                filters.skin_type is not None,
                bool(filters.brands),
                bool(filters.product_types),
                bool(filters.ingredients_include),
                bool(filters.ingredients_exclude),
            ]
        )
        multiplier = 5 + constraint_count * 10
        raw = self._vector_store.search(embedding, top_k=min(top_k * multiplier, 400))

        if exclude_id:
            raw = [(pid, s) for pid, s in raw if pid != exclude_id]

        top_similarity = raw[0][1] if raw else None

        docs = await self._product_repo.find_by_ids([pid for pid, _ in raw])
        doc_map = {d.id: d for d in docs if d.id}
        candidates = [(doc_map[pid], s) for pid, s in raw if pid in doc_map]

        kept, attrition = self._filter_with_attrition(candidates, filters)
        return kept[:top_k], attrition, len(candidates), top_similarity

    async def _hybrid(
        self,
        query: str,
        product_id: str | None,
        top_k: int,
        filters: RecommendationFilters,
    ) -> tuple[
        list[tuple[ProductDocument, float]], dict[str, int], int, float | None, dict[str, float]
    ]:
        """
        Blend semantic relevance with ingredient similarity.

        Uses Reciprocal Rank Fusion rather than max-normalised score blending.
        Max-normalisation made the top result score ~1.0 on every query however
        poor the match, so `score` looked like a confidence and wasn't one. RRF
        combines RANKINGS, which is stable across queries and doesn't fabricate
        a fake 1.0 at the top. Raw cosine similarity is preserved separately so
        the relevance floor still has something honest to threshold.
        """
        sem_results, attrition, n_candidates, top_sim = await self._semantic(
            query, top_k * 3, filters, exclude_id=product_id
        )
        similarity_map = {doc.id: s for doc, s in sem_results if doc.id}

        content_results: list[tuple[ProductDocument, float]] = []
        if product_id:
            content_results, _, _ = await self._content_based(product_id, top_k * 3, filters)

        if not content_results:
            return sem_results[:top_k], attrition, n_candidates, top_sim, similarity_map

        K = 60  # RRF damping constant — keeps tail ranks meaningful
        sem_w = settings.hybrid_semantic_weight
        con_w = settings.hybrid_content_weight

        fused: dict[str, float] = {}
        doc_map: dict[str, ProductDocument] = {}
        for rank, (doc, _) in enumerate(sem_results, start=1):
            if doc.id:
                fused[doc.id] = fused.get(doc.id, 0.0) + sem_w / (K + rank)
                doc_map[doc.id] = doc
        for rank, (doc, _) in enumerate(content_results, start=1):
            if doc.id:
                fused[doc.id] = fused.get(doc.id, 0.0) + con_w / (K + rank)
                doc_map[doc.id] = doc

        ordered = sorted(fused.items(), key=lambda x: x[1], reverse=True)
        results = [(doc_map[pid], score) for pid, score in ordered[:top_k] if pid in doc_map]
        return results, attrition, n_candidates, top_sim, similarity_map

    # ------------------------------------------------------------------
    # Relax suggestions — the way out of an over-constrained search
    # ------------------------------------------------------------------

    async def _relax_suggestions(
        self,
        filters: RecommendationFilters,
        current_count: int,
    ) -> list[RelaxSuggestion]:
        """
        For each active constraint, count what dropping it would return.

        The customer sees "+7 matches" on the button before they commit, which
        turns a dead end into a choice. Note we never offer to relax an
        ingredient exclusion — that is a safety rule, not a preference.
        """
        suggestions: list[RelaxSuggestion] = []
        labels = {
            "max_price": "Remove the budget limit",
            "min_price": "Remove the minimum price",
            "skin_type": "Ignore skin type",
            "product_types": "Any product type",
            "brands": "Any brand",
            "ingredients_include": "Drop the must-have ingredients",
        }
        for field, label in labels.items():
            value = getattr(filters, field, None)
            if not value:
                continue
            update = {field: [] if isinstance(value, list) else None}
            relaxed = filters.model_copy(update=update)
            count = await self._product_repo.count(self._build_mongo_filter(relaxed))
            if count > current_count:
                suggestions.append(
                    RelaxSuggestion(filter_name=field, label=label, result_count=count)
                )
        suggestions.sort(key=lambda s: s.result_count, reverse=True)
        return suggestions[:3]

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def recommend(self, request: RecommendRequest) -> RecommendResponse:
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        strategy = request.strategy
        filters = request.filters
        top_k = request.top_k
        similarity_map: dict[str, float] = {}
        top_similarity: float | None = None

        if strategy == RecommendationStrategy.CONTENT:
            if not request.product_id:
                raise ValidationError("product_id is required for content-based recommendations")
            results, attrition, n_candidates = await self._content_based(
                request.product_id, top_k, filters
            )
            query = None

        elif strategy == RecommendationStrategy.SEMANTIC:
            if not request.query:
                raise ValidationError("query is required for semantic recommendations")
            results, attrition, n_candidates, top_similarity = await self._semantic(
                request.query, top_k, filters
            )
            similarity_map = {doc.id: s for doc, s in results if doc.id}
            query = request.query

        else:  # HYBRID
            if not request.query:
                raise ValidationError("query is required for hybrid recommendations")
            (
                results,
                attrition,
                n_candidates,
                top_similarity,
                similarity_map,
            ) = await self._hybrid(request.query, request.product_id, top_k, filters)
            query = request.query

        if request.diversify and len(results) > 1:
            results = self._diversify(results, top_k, settings.max_per_brand_in_results)

        # --- the honesty layer -------------------------------------------
        low_confidence = False
        reason: str | None = None

        if not results:
            low_confidence = True
            reason = "no_results"
        elif len(results) < settings.min_results_before_low_confidence:
            low_confidence = True
            reason = "too_few_results"
        elif top_similarity is not None and top_similarity < settings.relevance_floor:
            # Nearest-neighbour search always returns something. Without this
            # branch the API would answer "iphone charger" with ten moisturisers.
            low_confidence = True
            reason = "below_relevance_floor"

        relax: list[RelaxSuggestion] = []
        if low_confidence and reason in ("no_results", "too_few_results"):
            relax = await self._relax_suggestions(filters, len(results))

        products = [
            doc_to_response(
                doc,
                score=score,
                similarity=similarity_map.get(doc.id or ""),
                filters=filters,
                rank=i,
            )
            for i, (doc, score) in enumerate(results, start=1)
        ]

        took_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "recommend request_id=%s strategy=%s results=%d low_confidence=%s took_ms=%d",
            request_id,
            strategy.value,
            len(products),
            low_confidence,
            took_ms,
        )

        return RecommendResponse(
            request_id=request_id,
            strategy=strategy,
            query=query,
            seed_product_id=request.product_id,
            total=len(products),
            products=products,
            filters_applied=filters,
            low_confidence=low_confidence,
            low_confidence_reason=reason,
            top_similarity=top_similarity,
            candidates_before_filters=n_candidates,
            filter_attrition=attrition,
            relax_suggestions=relax,
            took_ms=took_ms,
        )
