"""
Ingredient intelligence — the domain knowledge layer.

WHY THIS FILE EXISTS
--------------------
The raw dataset gives us ingredient names as free text. Three product
problems follow from that, and all three are solved here rather than
scattered through the services:

1. AVOIDANCE IS A SAFETY FEATURE, NOT A FILTER.
   A customer who says "no fragrance" means parfum, linalool, limonene,
   citronellol and geraniol too. Exact-string matching on "fragrance"
   catches none of them — `parfum` is the 3rd most common ingredient in
   this catalogue. AVOID_GROUPS maps a customer-facing avoidance into the
   full set of INCI names that satisfy it.

2. SEMANTIC SEARCH NEEDS CUSTOMER LANGUAGE.
   Customers type symptoms ("tight after washing", "shiny by lunchtime").
   Products are named after chemistry. ACTIVES maps known actives to the
   concerns they are commonly associated with, so that language can be
   folded into the embedded text at ingest time.

3. SKIN-TYPE FIT MUST CARRY A CONFIDENCE.
   We infer fit from ingredient presence. That is a heuristic — it knows
   nothing about concentration or formulation. Everything here returns a
   confidence alongside the label so the UI can say "often suited to"
   instead of "for your skin type".

Nothing in this file is a medical claim. Every phrase is about what an
ingredient is COMMONLY USED IN, never what it treats.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# 1. AVOIDANCE GROUPS
# --------------------------------------------------------------------------
# Keys are what the customer sees. Values are matched as SUBSTRINGS against
# normalised ingredient names, so "alcohol denat" also catches
# "alcohol denat.", "alcohol denatured", etc.
#
# NOTE ON HONESTY: this list is good, not complete. The UI must never claim
# a product is "fragrance-free" — only that "no fragrance ingredients were
# found in this product's published list". Different claim, different risk.

AVOID_GROUPS: dict[str, list[str]] = {
    "fragrance": [
        "parfum", "fragrance", "aroma", "linalool", "limonene", "citronellol",
        "geraniol", "citral", "eugenol", "coumarin", "benzyl salicylate",
        "benzyl benzoate", "benzyl cinnamate", "hexyl cinnamal", "farnesol",
        "isoeugenol", "amyl cinnamal", "hydroxycitronellal", "cinnamyl alcohol",
    ],
    "drying alcohol": [
        "alcohol denat", "sd alcohol", "ethanol", "isopropyl alcohol",
    ],
    "essential oils": [
        "lavandula", "rosmarinus", "mentha", "eucalyptus", "citrus aurantium",
        "citrus limon", "citrus sinensis", "melaleuca", "pelargonium",
        "cymbopogon", "eugenia caryophyllus", "essential oil",
    ],
    "silicones": [
        "dimethicon", "siloxane", "cyclopentasiloxane", "cyclohexasiloxane",
        "silsesquioxane", "dimethiconol", "trimethicone",
    ],
    "sulfates": [
        "sodium lauryl sulfate", "sodium laureth sulfate", "ammonium lauryl sulfate",
        "ammonium laureth sulfate", "sles", "sls",
    ],
    "parabens": [
        "paraben",
    ],
    "nut oils": [
        "prunus amygdalus", "sweet almond", "corylus avellana", "hazelnut",
        "macadamia", "juglans", "walnut", "carya", "pecan", "argania",
        "bertholletia", "brazil nut", "anacardium", "cashew", "pistacia",
    ],
    "coconut": [
        "cocos nucifera", "coconut", "cocamidopropyl", "cocamide", "coco-glucoside",
        "sodium cocoyl",
    ],
    "shea butter": [
        "butyrospermum", "shea",
    ],
    "salicylic acid": [
        "salicylic acid", "salix alba", "willow bark", "betaine salicylate",
    ],
    "retinoids": [
        "retinol", "retinal", "retinyl", "retinoate", "bakuchiol",
    ],
    "exfoliating acids": [
        "glycolic acid", "lactic acid", "mandelic acid", "salicylic acid",
        "malic acid", "tartaric acid", "citric acid", "azelaic acid",
    ],
    "mineral oil": [
        "paraffinum liquidum", "mineral oil", "petrolatum", "cera microcristallina",
    ],
    "gluten": [
        "triticum vulgare", "wheat", "hordeum", "barley", "avena sativa", "oat",
        "secale cereale", "rye",
    ],
}

# Aliases so a customer typing any of these hits the right group.
AVOID_ALIASES: dict[str, str] = {
    "perfume": "fragrance",
    "parfum": "fragrance",
    "scent": "fragrance",
    "fragrance free": "fragrance",
    "alcohol": "drying alcohol",
    "alcohol denat": "drying alcohol",
    "denatured alcohol": "drying alcohol",
    "eo": "essential oils",
    "essential oil": "essential oils",
    "silicone": "silicones",
    "dimethicone": "silicones",
    "sulfate": "sulfates",
    "sulphate": "sulfates",
    "sls": "sulfates",
    "paraben": "parabens",
    "nuts": "nut oils",
    "nut": "nut oils",
    "tree nuts": "nut oils",
    "almond": "nut oils",
    "shea": "shea butter",
    "bha": "salicylic acid",
    "retinoid": "retinoids",
    "retinol": "retinoids",
    "vitamin a": "retinoids",
    "aha": "exfoliating acids",
    "acids": "exfoliating acids",
    "acid": "exfoliating acids",
    "petrolatum": "mineral oil",
    "vaseline": "mineral oil",
}


def resolve_avoid_terms(user_term: str) -> tuple[str, list[str]]:
    """
    Turn what a customer typed into (group_label, [substrings to match]).

    Unknown terms fall through to a single-term substring match, which is
    still better than exact equality — "niacin" will catch "niacinamide".
    """
    key = (user_term or "").strip().lower()
    if not key:
        return "", []
    key = AVOID_ALIASES.get(key, key)
    if key in AVOID_GROUPS:
        return key, AVOID_GROUPS[key]
    return key, [key]


def find_matching_ingredients(ingredients: list[str], patterns: list[str]) -> list[str]:
    """Return the actual ingredient names in this product matching any pattern."""
    hits: list[str] = []
    for ing in ingredients:
        low = ing.lower()
        if any(p in low for p in patterns):
            hits.append(ing)
    return hits


def product_violates(ingredients: list[str], user_terms: list[str]) -> list[str]:
    """
    Return the customer-facing labels this product violates.

    Empty list means the product passed every avoidance rule. This is the
    single most safety-relevant function in the codebase — it decides what
    a customer with an allergy is allowed to see.
    """
    violated: list[str] = []
    for term in user_terms:
        label, patterns = resolve_avoid_terms(term)
        if patterns and find_matching_ingredients(ingredients, patterns):
            violated.append(label or term)
    return violated


# --------------------------------------------------------------------------
# 2. ACTIVES → CONCERNS, SKIN TYPES, AND PLAIN-ENGLISH DESCRIPTION
# --------------------------------------------------------------------------
# `blurb` is deliberately written as "commonly used in products aimed at X",
# never "treats X". These strings are surfaced directly in the UI, so the
# hedging has to live in the data, not in a wrapper somewhere downstream.

ACTIVES: dict[str, dict] = {
    "hyaluronic acid": {
        "match": ["hyaluronic", "sodium hyaluronate", "hydrolyzed hyaluronic"],
        "concerns": ["dryness", "dehydration", "plumpness"],
        "skin_types": ["dry", "combination", "normal", "sensitive"],
        "blurb": "a humectant commonly used in products aimed at dehydrated skin",
    },
    "glycerin": {
        "match": ["glycerin", "glycerol"],
        "concerns": ["dryness", "dehydration"],
        "skin_types": ["dry", "normal", "combination", "sensitive"],
        "blurb": "a widely used humectant that helps products feel hydrating",
        "weak_signal": True,  # present in ~50-70% of the catalogue: identifies a formula, cannot discriminate skin type
    },
    "ceramides": {
        "match": ["ceramide", "phytosphingosine", "cholesterol"],
        "concerns": ["dryness", "barrier", "sensitivity", "flaking"],
        "skin_types": ["dry", "sensitive", "normal"],
        "blurb": "a barrier lipid commonly found in barrier-repair moisturisers",
    },
    "niacinamide": {
        "match": ["niacinamide", "nicotinamide"],
        "concerns": ["oiliness", "pores", "uneven tone", "dullness", "redness"],
        "skin_types": ["oily", "combination", "normal"],
        "blurb": "commonly used in products aimed at oiliness and uneven tone",
    },
    "salicylic acid": {
        "match": ["salicylic acid", "salix alba", "betaine salicylate"],
        "concerns": ["breakouts", "blackheads", "oiliness", "pores"],
        "skin_types": ["oily", "combination"],
        "blurb": "a BHA commonly used in products aimed at breakout-prone skin",
    },
    "glycolic acid": {
        "match": ["glycolic acid"],
        "concerns": ["dullness", "texture", "uneven tone"],
        "skin_types": ["normal", "oily", "combination"],
        "blurb": "an AHA commonly used in products aimed at surface texture",
    },
    "lactic acid": {
        "match": ["lactic acid"],
        "concerns": ["dullness", "texture", "dryness"],
        "skin_types": ["dry", "normal"],
        "blurb": "a gentler AHA often found in resurfacing products",
    },
    "retinol": {
        "match": ["retinol", "retinal", "retinyl", "retinoate"],
        "concerns": ["fine lines", "ageing", "texture", "breakouts"],
        "skin_types": ["normal", "oily", "combination"],
        "blurb": "a vitamin A derivative commonly found in anti-ageing ranges",
    },
    "vitamin c": {
        "match": ["ascorbic acid", "ascorbyl", "ascorbate", "3-o-ethyl ascorbic"],
        "concerns": ["dullness", "dark spots", "uneven tone", "brightness"],
        "skin_types": ["normal", "combination", "oily"],
        "blurb": "an antioxidant commonly used in brightening products",
    },
    "vitamin e": {
        "match": ["tocopherol", "tocopheryl"],
        "concerns": ["dryness", "antioxidant"],
        "skin_types": ["dry", "normal"],
        "blurb": "an antioxidant widely used to help protect oils in a formula",
        "weak_signal": True,  # present in ~50-70% of the catalogue: identifies a formula, cannot discriminate skin type
    },
    "centella": {
        "match": ["centella", "madecassoside", "asiaticoside", "cica"],
        "concerns": ["redness", "sensitivity", "barrier", "irritation"],
        "skin_types": ["sensitive", "dry", "normal"],
        "blurb": "commonly used in products aimed at visibly sensitised skin",
    },
    "panthenol": {
        "match": ["panthenol", "pantothenic"],
        "concerns": ["dryness", "sensitivity", "barrier"],
        "skin_types": ["sensitive", "dry", "normal"],
        "blurb": "a soothing humectant often found in calming formulas",
    },
    "aloe": {
        "match": ["aloe"],
        "concerns": ["redness", "sensitivity", "dryness"],
        "skin_types": ["sensitive", "normal", "oily"],
        "blurb": "a plant extract widely used in cooling and calming products",
    },
    "allantoin": {
        "match": ["allantoin"],
        "concerns": ["sensitivity", "roughness"],
        "skin_types": ["sensitive", "dry"],
        "blurb": "a conditioning ingredient common in gentle formulas",
    },
    "colloidal oatmeal": {
        "match": ["avena sativa", "colloidal oat", "oat kernel"],
        "concerns": ["sensitivity", "dryness", "itchiness"],
        "skin_types": ["sensitive", "dry"],
        "blurb": "commonly found in products aimed at easily irritated skin",
    },
    "squalane": {
        "match": ["squalane", "squalene"],
        "concerns": ["dryness", "barrier"],
        "skin_types": ["dry", "normal", "combination"],
        "blurb": "a lightweight emollient common in facial oils and moisturisers",
    },
    "shea butter": {
        "match": ["butyrospermum"],
        "concerns": ["dryness", "flaking"],
        "skin_types": ["dry"],
        "blurb": "a rich butter common in products aimed at very dry skin",
    },
    "urea": {
        "match": ["urea"],
        "concerns": ["dryness", "roughness", "flaking"],
        "skin_types": ["dry"],
        "blurb": "a humectant often used in products aimed at rough, dry skin",
    },
    "clay": {
        "match": ["kaolin", "bentonite", "montmorillonite", "illite", "clay"],
        "concerns": ["oiliness", "pores", "blackheads"],
        "skin_types": ["oily", "combination"],
        "blurb": "an absorbent mineral common in products aimed at oily skin",
    },
    "charcoal": {
        "match": ["charcoal", "carbo activatus"],
        "concerns": ["oiliness", "pores"],
        "skin_types": ["oily", "combination"],
        "blurb": "commonly used in deep-cleansing and clarifying formulas",
    },
    "zinc": {
        "match": ["zinc pca", "zinc oxide", "zinc gluconate"],
        "concerns": ["oiliness", "breakouts", "sun protection"],
        "skin_types": ["oily", "combination", "sensitive"],
        "blurb": "used both as a mineral sunscreen filter and in clarifying products",
    },
    "tea tree": {
        "match": ["melaleuca"],
        "concerns": ["breakouts", "oiliness"],
        "skin_types": ["oily", "combination"],
        "blurb": "a plant extract common in products aimed at blemish-prone skin",
    },
    "witch hazel": {
        "match": ["hamamelis"],
        "concerns": ["oiliness", "pores"],
        "skin_types": ["oily", "combination"],
        "blurb": "an astringent extract often found in toners",
    },
    "caffeine": {
        "match": ["caffeine", "caffeinee"],
        "concerns": ["puffiness", "dark circles"],
        "skin_types": ["normal", "combination"],
        "blurb": "commonly used in eye products aimed at the look of puffiness",
    },
    "peptides": {
        "match": ["peptide", "palmitoyl tripeptide", "matrixyl", "acetyl hexapeptide"],
        "concerns": ["fine lines", "ageing", "firmness"],
        "skin_types": ["normal", "dry", "combination"],
        "blurb": "commonly found in products aimed at firmness and fine lines",
    },
    "spf filters": {
        "match": ["homosalate", "octocrylene", "avobenzone", "butyl methoxydibenzoylmethane",
                  "ethylhexyl salicylate", "octinoxate", "titanium dioxide", "tinosorb",
                  "uvinul", "ensulizole"],
        "concerns": ["sun protection"],
        "skin_types": ["all"],
        "blurb": "contains UV filters, so this product offers sun protection",
    },
}

# Product type → concerns it naturally serves. Gives every product at least
# some customer-language text even when it has no recognised actives.
TYPE_CONCERNS: dict[str, list[str]] = {
    "cleanser": ["cleansing", "makeup removal", "daily routine"],
    "moisturiser": ["dryness", "hydration", "barrier", "daily routine"],
    "serum": ["targeted treatment", "concentrated"],
    "toner": ["prep", "balance", "daily routine"],
    "mask": ["weekly treatment", "intensive"],
    "exfoliator": ["dullness", "texture", "blackheads"],
    "peel": ["dullness", "texture", "uneven tone"],
    "oil": ["dryness", "nourishment", "glow"],
    "balm": ["dryness", "protection", "soothing"],
    "mist": ["refresh", "hydration", "on the go"],
    "eye care": ["dark circles", "puffiness", "fine lines", "eye area"],
    "body wash": ["body", "cleansing", "shower"],
    "bath oil": ["body", "dryness", "bath"],
    "bath salts": ["body", "bath", "relaxing"],
}


def analyse_ingredients(ingredients: list[str], product_type: str) -> dict:
    """
    Derive concerns, skin-type fit, key actives and a confidence score.

    Confidence is deliberately conservative:
      - 0.0  nothing recognised          → do NOT show a skin-type claim
      - 0.4  one recognised active       → "may suit", show with a caveat
      - 0.7  two or three                → "often suited to"
      - 0.9  four or more                → "often suited to", stronger wording
    It is never 1.0. We did not verify anything; the brand did not tell us.
    """
    joined = " ".join(ingredients).lower()
    key_actives: list[dict] = []
    concerns: set[str] = set()
    skin_votes: dict[str, int] = {}

    for name, spec in ACTIVES.items():
        if any(m in joined for m in spec["match"]):
            key_actives.append({"name": name, "blurb": spec["blurb"]})
            concerns.update(spec["concerns"])
            # Near-universal ingredients are still worth showing on the card,
            # but they must not vote on skin-type fit. Glycerin appears in ~72%
            # of this catalogue — letting it vote made almost every product
            # "suited to normal skin", which makes the filter meaningless.
            if spec.get("weak_signal"):
                continue
            for st in spec["skin_types"]:
                skin_votes[st] = skin_votes.get(st, 0) + 1

    ptype = (product_type or "").strip().lower()
    concerns.update(TYPE_CONCERNS.get(ptype, []))

    strong = [a for a in key_actives if not ACTIVES[a["name"]].get("weak_signal")]
    n = len(strong)
    confidence = 0.0 if n == 0 else 0.4 if n == 1 else 0.7 if n <= 3 else 0.9

    if skin_votes:
        top = max(skin_votes.values())
        # Keep any skin type with at least half the winning vote count, so a
        # product isn't pigeonholed by a single ingredient.
        skin_types = sorted(k for k, v in skin_votes.items() if v >= max(1, top / 2))
    else:
        skin_types = []

    return {
        "key_actives": key_actives[:6],
        "concerns": sorted(concerns),
        "skin_types": skin_types,
        "skin_type_confidence": confidence,
    }
