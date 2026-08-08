"""
Text normalisation for the preprocessing pipeline.

WHAT CHANGED AND WHY
--------------------
1. `extract_brand` now returns a CONFIDENCE alongside the brand. Brand is not
   in the dataset — it is guessed from the product name. The UI needs to know
   which guesses to mark as derived, so the guess and its reliability travel
   together instead of the reliability being lost.

2. `infer_skin_types` is gone. The old version appended "all" to every product
   that matched anything (so "all" meant nothing) and only assigned "normal"
   when NOTHING matched — meaning the "normal" bucket actually held the
   UNCLASSIFIED products, the opposite of what a customer selecting "normal"
   expects. Skin-type inference now lives in `ingredient_intel.analyse_ingredients`
   and returns a confidence with it.

3. `build_search_text` now includes concern language. Previously the embedded
   text was name + type + brand + chemistry, so a query like "soothing for
   redness" could only match on how close those words sit to ingredient names
   in general language. Folding in the concerns each active is associated with
   gives the embedding actual customer vocabulary to match against. This is the
   single biggest retrieval-quality change in the re-ingest.
"""

import ast
import re
from typing import Any

# Brands that appear in this catalogue and cannot be recovered from the first
# token of the product name (multi-word, punctuated, or ambiguous).
KNOWN_BRANDS = [
    "the ordinary", "the inkey list", "the chemistry brand", "first aid beauty",
    "la roche-posay", "la roche posay", "elizabeth arden", "est\u00e9e lauder",
    "estee lauder", "dr. jart+", "dr jart", "kiehl's", "ole henriksen",
    "paula's choice", "bare minerals", "bareminerals", "super facialist",
    "skin doctors", "egyptian magic", "neutrogena", "clinique", "cerave",
    "origins", "elemis", "aveno", "avene", "av\u00e8ne", "weleda", "bulldog",
    "embryolisse", "jason", "prai", "ameliorate", "eucerin", "garnier",
    "l'oreal", "l'or\u00e9al", "nivea", "vichy", "bioderma", "caudalie",
    "murad", "dermalogica", "medik8", "pixi", "revolution", "nip + fab",
    "nip+fab", "sanctuary spa", "soap & glory", "st. tropez", "st tropez",
    "this works", "rituals", "l'occitane", "aesop", "sunday riley",
    "drunk elephant", "glow recipe", "the body shop", "tropic",
]


def normalize_text(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    if not text or not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def parse_ingredients(raw: Any) -> list[str]:
    """Parse an ingredient list out of the CSV's stringified-list column."""
    if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
        return []
    if isinstance(raw, list):
        return [normalize_text(i) for i in raw if i]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [normalize_text(i) for i in parsed if i]
    except (ValueError, SyntaxError):
        pass
    return [normalize_text(i) for i in text.split(",") if i.strip()]


def extract_brand(product_name: str) -> tuple[str, float]:
    """
    Guess the brand from the product name.

    Returns (brand, confidence):
      1.0  matched a known brand in our list      -> safe to show plainly
      0.5  "The X" pattern, probably right        -> show with a derived marker
      0.3  first word of the name, a real guess   -> show with a derived marker
      0.0  nothing usable
    """
    name_lower = normalize_text(product_name)
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        if name_lower.startswith(brand):
            return brand.title(), 1.0

    tokens = product_name.split()
    if not tokens:
        return "Unknown", 0.0
    if len(tokens) >= 2 and tokens[0].lower() == "the":
        return f"{tokens[0]} {tokens[1]}".title(), 0.5
    return tokens[0].title(), 0.3


def build_search_text(
    product_name: str,
    product_type: str,
    brand: str,
    ingredients: list[str],
    concerns: list[str] | None = None,
    active_names: list[str] | None = None,
) -> str:
    """
    Build the string that gets embedded.

    Order matters a little: name and type first so short, high-signal tokens
    aren't drowned by a 40-item ingredient list; concerns next because that is
    the language customers actually type; raw chemistry last.
    """
    parts = [
        product_name,
        product_type,
        brand,
        " ".join(concerns or []),
        " ".join(active_names or []),
        " ".join(ingredients[:30]),
    ]
    return normalize_text(" | ".join(p for p in parts if p))
