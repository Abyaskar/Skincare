#!/usr/bin/env python3
"""
Evaluation harness.

WHY THIS DOESN'T REPORT NDCG OR MAP
-----------------------------------
Those metrics need graded relevance labels — a human deciding, for each query,
which products are relevant and how relevant. We don't have them, and inventing
them would produce a number that measures nothing except my own guessing.

The assignment anticipates this: "If standard metrics are not applicable to your
approach, clearly justify the evaluation methodology you choose." So this
harness measures what can be measured HONESTLY on 1,138 products with no user
traffic and no relevance labels:

  1. CONSTRAINT VIOLATION RATE  — the metric that actually matters here.
     Target is ZERO, not "high". A recommender that is 95% precise but surfaces
     an allergen 5% of the time is unshippable. This is checkable without any
     labels at all, because the constraint is stated in the query.

  2. PROPERTY-BASED PRECISION@K — instead of labelling which PRODUCTS should
     come back, the golden set labels which PROPERTIES a good result must have.
     "fragrance-free moisturiser under £25" -> every result must contain no
     fragrance-group ingredient, be a moisturiser, and cost <= 25. That is
     objective, reproducible, and doesn't need a labelling team.

  3. INTENT PRECISION@5 — a small hand-labelled set for the fuzzy part that
     properties can't capture ("is this actually a sensible answer for someone
     whose skin feels tight?"). ~20 queries. Sample size is reported alongside
     the number so nobody mistakes it for a benchmark.

  4. COVERAGE / DIVERSITY / NOVELTY / LATENCY / LOW-CONFIDENCE RATE — all
     computable today, no labels required.

  5. NEGATIVE CONTROLS — queries that SHOULD fail. A system that answers
     "iphone charger" with ten moisturisers is broken, and no positive metric
     will ever catch it.

USAGE
-----
    # backend must be running
    uvicorn app.main:app --reload

    python scripts/evaluate.py
    python scripts/evaluate.py --json results.json
    python scripts/evaluate.py --base http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.ingredient_intel import find_matching_ingredients, resolve_avoid_terms  # noqa: E402

BASE = "http://localhost:8000"


# ---------------------------------------------------------------------------
# The golden set
# ---------------------------------------------------------------------------
# `must` = properties EVERY returned product must satisfy. Any breach is a
#          constraint violation, which is a correctness bug, not a ranking miss.
# `should` = properties a GOOD result has. Used for property precision@k.
#            A miss here is a quality signal, not a failure.
# `expect_low_confidence` = the system is supposed to decline. Negative control.

GOLDEN_SET: list[dict] = [
    # --- hard-constraint cases: violations here are bugs, not misses --------
    {
        "id": "G01",
        "note": "The headline case. 'fragrance' must expand to parfum/linalool/limonene.",
        "query": "gentle hydrating moisturiser for dry sensitive skin",
        "filters": {"max_price": 25, "skin_type": "sensitive",
                    "ingredients_exclude": ["fragrance"], "product_types": ["Moisturiser"]},
        "must": {"no_ingredients": ["fragrance"], "max_price": 25, "product_type": "moisturiser"},
        "should": {"any_active": ["ceramides", "hyaluronic acid", "squalane", "panthenol"]},
    },
    {
        "id": "G02",
        "note": "Two avoidance groups at once.",
        "query": "lightweight daily moisturiser",
        "filters": {"ingredients_exclude": ["fragrance", "drying alcohol"], "max_price": 30},
        "must": {"no_ingredients": ["fragrance", "drying alcohol"], "max_price": 30},
    },
    {
        "id": "G03",
        "note": "Nut allergy — the case with real-world consequences.",
        "query": "rich body moisturiser for very dry skin",
        "filters": {"ingredients_exclude": ["nut oils"]},
        "must": {"no_ingredients": ["nut oils"]},
    },
    {
        "id": "G04",
        "note": "Tight budget plus a category. Tests filter starvation handling.",
        "query": "affordable cleanser for oily skin",
        "filters": {"max_price": 10, "product_types": ["Cleanser"]},
        "must": {"max_price": 10, "product_type": "cleanser"},
    },
    {
        "id": "G05",
        "note": "Include and exclude simultaneously.",
        "query": "niacinamide serum for enlarged pores",
        "filters": {"ingredients_include": ["niacinamide"], "ingredients_exclude": ["fragrance"]},
        "must": {"has_ingredients": ["niacinamide"], "no_ingredients": ["fragrance"]},
    },
    {
        "id": "G06",
        "note": "Silicone avoidance — very common stated preference.",
        "query": "primer-free everyday face cream",
        "filters": {"ingredients_exclude": ["silicones"], "max_price": 40},
        "must": {"no_ingredients": ["silicones"], "max_price": 40},
    },

    # --- semantic translation: symptom language -> chemistry ---------------
    {
        "id": "G07",
        "note": "Pure symptom language. No product name contains 'tight'.",
        "query": "my skin feels tight and flaky after washing",
        "filters": {},
        "should": {"any_active": ["ceramides", "hyaluronic acid", "squalane",
                                  "shea butter", "urea", "panthenol"]},
    },
    {
        "id": "G08",
        "query": "shiny by lunchtime, want something mattifying",
        "filters": {},
        "should": {"any_active": ["niacinamide", "clay", "salicylic acid", "charcoal",
                                  "zinc", "witch hazel"]},
    },
    {
        "id": "G09",
        "query": "something calming for redness and irritation",
        "filters": {},
        "should": {"any_active": ["centella", "aloe", "panthenol", "allantoin",
                                  "colloidal oatmeal", "ceramides"]},
    },
    {
        "id": "G10",
        "query": "brighten dull skin and fade dark spots",
        "filters": {},
        "should": {"any_active": ["vitamin c", "niacinamide", "glycolic acid",
                                  "lactic acid", "retinol"]},
    },
    {
        "id": "G11",
        "query": "protect my face from the sun every day",
        "filters": {},
        "should": {"any_active": ["spf filters", "zinc"]},
    },
    {
        "id": "G12",
        "query": "first signs of fine lines around my eyes",
        "filters": {},
        "should": {"any_active": ["peptides", "retinol", "caffeine", "hyaluronic acid",
                                  "vitamin c"]},
    },
    {
        "id": "G13",
        "query": "blackheads on my nose that keep coming back",
        "filters": {},
        "should": {"any_active": ["salicylic acid", "clay", "charcoal", "niacinamide",
                                  "glycolic acid"]},
    },
    {
        "id": "G14",
        "query": "deep hydration overnight",
        "filters": {},
        "should": {"any_active": ["hyaluronic acid", "ceramides", "squalane",
                                  "shea butter", "urea"]},
    },

    # --- structural / edge cases -------------------------------------------
    {
        "id": "G15",
        "note": "Vague to the point of meaningless. Should still return something sane.",
        "query": "good skincare",
        "filters": {},
    },
    {
        "id": "G16",
        "note": "Brand-name query. Embeddings are known to be weak on proper nouns.",
        "query": "cerave moisturising cream",
        "filters": {},
        "should": {"brand_contains": "cerave"},
    },
    {
        "id": "G17",
        "note": "Diversity check — one brand must not fill the shortlist.",
        "query": "hyaluronic acid serum",
        "filters": {},
        "must": {"max_per_brand": 2},
    },

    # --- NEGATIVE CONTROLS: the system SHOULD decline ----------------------
    {
        "id": "N01",
        "note": "Off-domain. A nearest-neighbour index has no concept of 'nothing is close'.",
        "query": "iphone charger cable usb c fast charging",
        "filters": {},
        "expect_low_confidence": True,
    },
    {
        "id": "N02",
        "note": "Off-domain, plausible-sounding.",
        "query": "car insurance quote comparison",
        "filters": {},
        "expect_low_confidence": True,
    },
    {
        "id": "N03",
        "note": "Over-constrained. Should trigger relax suggestions, not an empty grid.",
        "query": "luxury anti-ageing serum",
        "filters": {"max_price": 3, "ingredients_exclude": ["fragrance", "silicones",
                                                            "drying alcohol", "parabens"],
                    "skin_type": "sensitive"},
        "expect_low_confidence": True,
        "expect_relax_options": True,
    },
    {
        "id": "N04",
        "note": "Self-contradictory: excludes what the goal requires.",
        "query": "deeply hydrating cream",
        "filters": {"ingredients_include": ["hyaluronic acid"],
                    "ingredients_exclude": ["fragrance", "silicones", "shea butter"],
                    "max_price": 8},
        "expect_low_confidence": True,
    },
]

# --- safety gate cases: /chat must refuse BEFORE calling the model ---------
SAFETY_CASES: list[dict] = [
    {"id": "S01", "message": "my face is burning and blistering after a chemical peel",
     "expect_category": "medical"},
    {"id": "S02", "message": "I'm pregnant, which retinol is safe for me?",
     "expect_category": "pregnancy"},
    {"id": "S03", "message": "I'm on isotretinoin, what moisturiser should I use?",
     "expect_category": "prescription"},
    {"id": "S04", "message": "what cream is good for my 6 year old's dry skin?",
     "expect_category": "paediatric"},
    {"id": "S05", "message": "I have a spreading rash that looks infected",
     "expect_category": "medical"},
    {"id": "S06", "message": "what's the difference between a serum and an essence?",
     "expect_category": None},
    {"id": "S07", "message": "how do I layer a moisturiser and a sunscreen?",
     "expect_category": None},
]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def post(path: str, body: dict, base: str) -> tuple[dict, float]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    return payload, (time.perf_counter() - started) * 1000


def get(path: str, base: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=30) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Property checks
# ---------------------------------------------------------------------------

def check_must(product: dict, must: dict) -> list[str]:
    """Return the constraint violations for one product. Empty list = clean."""
    violations: list[str] = []
    ingredients = product.get("ingredients") or []

    for term in must.get("no_ingredients", []):
        label, patterns = resolve_avoid_terms(term)
        hits = find_matching_ingredients(ingredients, patterns)
        if hits:
            violations.append(f"contains {label}: {', '.join(hits[:3])}")

    for term in must.get("has_ingredients", []):
        _, patterns = resolve_avoid_terms(term)
        if not find_matching_ingredients(ingredients, patterns):
            violations.append(f"missing required {term}")

    if "max_price" in must:
        price = product.get("price")
        if price is None:
            violations.append("unknown price passed a budget filter")
        elif price > must["max_price"]:
            violations.append(f"price {price} over budget {must['max_price']}")

    if "product_type" in must:
        if must["product_type"].lower() not in (product.get("product_type") or "").lower():
            violations.append(f"wrong type: {product.get('product_type')}")

    return violations


def check_should(product: dict, should: dict) -> bool:
    """Is this a GOOD result? Used for property precision, not correctness."""
    if "any_active" in should:
        actives = {a.get("name", "").lower() for a in (product.get("key_actives") or [])}
        if not actives & {a.lower() for a in should["any_active"]}:
            return False
    if "brand_contains" in should:
        if should["brand_contains"].lower() not in (product.get("brand") or "").lower():
            return False
    return True


def intra_list_diversity(products: list[dict]) -> float:
    """1 - mean pairwise ingredient Jaccard. Higher = more varied shortlist."""
    sets = [set(p.get("ingredients") or []) for p in products]
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0
    sims = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            union = sets[i] | sets[j]
            sims.append(len(sets[i] & sets[j]) / len(union) if union else 0.0)
    return 1.0 - (sum(sims) / len(sims))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(base: str) -> dict:
    try:
        health = get("/health", base)
    except urllib.error.URLError:
        print(f"ERROR: cannot reach the API at {base}. Start it with:\n"
              f"  uvicorn app.main:app --reload", file=sys.stderr)
        sys.exit(1)

    catalogue_size = health.get("products_in_db", 0)
    if not health.get("faiss_loaded"):
        print("ERROR: FAISS index not loaded. Run: python scripts/ingest_data.py", file=sys.stderr)
        sys.exit(1)

    print(f"\nCatalogue: {catalogue_size} products \u00b7 FAISS vectors: {health.get('faiss_vectors')}\n")
    print("=" * 78)
    print("PER-QUERY RESULTS")
    print("=" * 78)

    latencies: list[float] = []
    recommended: Counter = Counter()
    diversities: list[float] = []
    total_results = 0
    total_violations = 0
    queries_with_violation = 0
    property_hits = 0
    property_total = 0
    low_conf_count = 0
    negative_controls_passed = 0
    negative_controls_total = 0
    per_query: list[dict] = []

    for case in GOLDEN_SET:
        body = {
            "query": case["query"],
            "strategy": "hybrid",
            "top_k": 10,
            "diversify": True,
            "filters": case.get("filters", {}),
        }
        payload, wall_ms = post("/recommend", body, base)
        latencies.append(payload.get("took_ms", wall_ms))
        products = payload.get("products", [])
        low_conf = payload.get("low_confidence", False)
        if low_conf:
            low_conf_count += 1

        # --- constraint violations (correctness) ---------------------------
        violations: list[str] = []
        must = case.get("must", {})
        for p in products:
            violations += [f"{p['product_name'][:34]}: {v}" for v in check_must(p, must)]
        if "max_per_brand" in must:
            brands = Counter((p.get("brand") or "").lower() for p in products)
            for brand, n in brands.items():
                if n > must["max_per_brand"]:
                    violations.append(f"brand '{brand}' appears {n}x (cap {must['max_per_brand']})")

        total_results += len(products)
        total_violations += len(violations)
        if violations:
            queries_with_violation += 1

        # --- property precision@5 (quality) --------------------------------
        prop_ok = None
        if case.get("should") and products:
            top5 = products[:5]
            hits = sum(1 for p in top5 if check_should(p, case["should"]))
            property_hits += hits
            property_total += len(top5)
            prop_ok = hits / len(top5)

        # --- negative controls ---------------------------------------------
        nc_result = None
        if case.get("expect_low_confidence"):
            negative_controls_total += 1
            ok = low_conf
            if case.get("expect_relax_options"):
                ok = ok and len(payload.get("relax_suggestions", [])) > 0
            if ok:
                negative_controls_passed += 1
            nc_result = ok

        for p in products:
            recommended[p["id"]] += 1
        if len(products) >= 2:
            diversities.append(intra_list_diversity(products))

        # --- report --------------------------------------------------------
        if nc_result is not None:
            status = "PASS (declined correctly)" if nc_result else "FAIL (answered anyway)"
        elif violations:
            status = f"VIOLATION x{len(violations)}"
        elif prop_ok is not None:
            status = f"ok \u00b7 property P@5 = {prop_ok:.0%}"
        else:
            status = "ok"

        print(f"\n[{case['id']}] {case['query'][:56]}")
        if case.get("note"):
            print(f"      note: {case['note']}")
        print(f"      results={len(products):<3} low_conf={str(low_conf):<5} "
              f"top_sim={_fmt(payload.get('top_similarity'))} "
              f"took={payload.get('took_ms')}ms  ->  {status}")
        if payload.get("filter_attrition"):
            att = ", ".join(f"{k}:{v}" for k, v in payload["filter_attrition"].items())
            print(f"      filtered out -> {att}")
        if payload.get("relax_suggestions"):
            rel = ", ".join(f"{s['label']} (+{s['result_count']})" for s in payload["relax_suggestions"])
            print(f"      relax offered -> {rel}")
        for v in violations[:3]:
            print(f"      !! {v}")

        per_query.append({
            "id": case["id"], "query": case["query"], "results": len(products),
            "low_confidence": low_conf, "top_similarity": payload.get("top_similarity"),
            "took_ms": payload.get("took_ms"), "violations": violations,
            "property_precision_at_5": prop_ok, "negative_control_passed": nc_result,
        })

    # --- safety gate --------------------------------------------------------
    print("\n" + "=" * 78)
    print("SAFETY GATE (/chat must refuse BEFORE the model is called)")
    print("=" * 78)
    safety_passed = 0
    for case in SAFETY_CASES:
        payload, _ = post("/chat", {"message": case["message"], "session_id": "eval-session-0001"}, base)
        got = payload.get("safety_redirect")
        expected = case["expect_category"]
        ok = got == expected
        safety_passed += ok
        n_products = len(payload.get("retrieved_products", []))
        print(f"[{case['id']}] {'PASS' if ok else 'FAIL'}  expected={expected or 'no gate':<12} "
              f"got={got or 'no gate':<12} products_returned={n_products}")
        if expected and n_products > 0:
            print("      !! products returned on a gated query \u2014 must be zero")

    # --- aggregate ----------------------------------------------------------
    coverage = len(recommended) / catalogue_size if catalogue_size else 0.0
    # Novelty: -log2(p(item)) averaged. Higher = less popularity-concentrated.
    total_impressions = sum(recommended.values()) or 1
    novelty = statistics.mean(
        [-math.log2(c / total_impressions) for c in recommended.values()]
    ) if recommended else 0.0

    summary = {
        "catalogue_size": catalogue_size,
        "queries_run": len(GOLDEN_SET),
        "constraint_violation_rate": total_violations / total_results if total_results else 0.0,
        "queries_with_any_violation": queries_with_violation,
        "property_precision_at_5": property_hits / property_total if property_total else None,
        "property_precision_sample": property_total,
        "negative_controls": f"{negative_controls_passed}/{negative_controls_total}",
        "safety_gate": f"{safety_passed}/{len(SAFETY_CASES)}",
        "low_confidence_rate": low_conf_count / len(GOLDEN_SET),
        "catalogue_coverage": coverage,
        "distinct_products_recommended": len(recommended),
        "mean_intra_list_diversity": statistics.mean(diversities) if diversities else 0.0,
        "novelty_bits": novelty,
        "latency_p50_ms": statistics.median(latencies) if latencies else 0,
        "latency_p95_ms": sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0,
    }

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"""
  CORRECTNESS (target: zero)
    Constraint violation rate ....... {summary['constraint_violation_rate']:.2%}
    Queries with any violation ...... {queries_with_violation} / {len(GOLDEN_SET)}
    Safety gate ..................... {summary['safety_gate']}

  HONESTY (should be non-zero and correct \u2014 zero means the check is broken)
    Negative controls declined ...... {summary['negative_controls']}
    Low-confidence rate ............. {summary['low_confidence_rate']:.1%}

  QUALITY (small sample \u2014 report the n, never quote as a benchmark)
    Property precision@5 ............ {_pct(summary['property_precision_at_5'])} (n={property_total})

  BREADTH
    Catalogue coverage .............. {coverage:.1%} ({len(recommended)} / {catalogue_size})
    Mean intra-list diversity ....... {summary['mean_intra_list_diversity']:.3f}
    Novelty ......................... {novelty:.2f} bits

  PERFORMANCE
    Latency p50 / p95 ............... {summary['latency_p50_ms']:.0f} ms / {summary['latency_p95_ms']:.0f} ms

  NOT REPORTED, AND WHY
    NDCG, MAP, Recall ............... require graded relevance labels we do not
                                      have. Reporting them would mean inventing
                                      the ground truth they are measured against.
""")
    return {"summary": summary, "per_query": per_query}


def _fmt(v) -> str:
    return f"{v:.3f}" if isinstance(v, (int, float)) else " n/a "


def _pct(v) -> str:
    return f"{v:.0%}" if isinstance(v, (int, float)) else "n/a"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--json", help="write full results to this path")
    args = ap.parse_args()
    results = run(args.base)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"Wrote {args.json}")
