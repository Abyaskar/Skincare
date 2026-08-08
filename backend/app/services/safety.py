"""
Deterministic safety gate and claim checker for anything the LLM touches.

WHY DETERMINISTIC
-----------------
Someone describing a burning, blistering or spreading reaction needs a doctor,
not a moisturiser. That decision is too important to hand to a model whose
output varies run to run. A keyword gate is crude, but it is predictable, it is
auditable, and it runs BEFORE the model is called — so there is no path where a
clever prompt gets around it.

Tuned for HIGH RECALL, accepting low precision. An unnecessary "please check
with a professional" is a minor annoyance. A missed one is not.
"""

from __future__ import annotations

import re

# --- Route to a human, return no products ---------------------------------
MEDICAL_PATTERNS = [
    r"\bburn(s|ing|ed)?\b", r"\bblister", r"\bbleed", r"\binfect", r"\bpus\b",
    r"\bswollen\b", r"\bswelling\b", r"\brash\b.*\bspread", r"\bspreading\b",
    r"\bhives\b", r"\banaphyla", r"\bchemical burn\b", r"\bscab", r"\bulcer",
    r"\bmole\b", r"\bmelanoma\b", r"\bcancer\b", r"\bbiopsy\b", r"\blesion\b",
    r"\beczema\b", r"\bpsoriasis\b", r"\brosacea\b", r"\bdermatitis\b",
    r"\bstaph\b", r"\bimpetigo\b", r"\bcellulitis\b", r"\bshingles\b",
    r"\ballergic reaction\b", r"\breacted badly\b", r"\bemergency\b",
]
PRESCRIPTION_PATTERNS = [
    r"\bisotretinoin\b", r"\baccutane\b", r"\btretinoin\b", r"\bretin-a\b",
    r"\badapalene\b", r"\bdifferin\b", r"\bhydroquinone\b", r"\bspironolactone\b",
    r"\bantibiotic", r"\bsteroid\b", r"\bhydrocortisone\b", r"\bprescription\b",
    r"\bmy dermatologist prescribed\b", r"\bdoxycycline\b",
]
PREGNANCY_PATTERNS = [
    r"\bpregnan", r"\bbreastfeed", r"\bnursing\b", r"\btrying to conceive\b",
    r"\bivf\b", r"\bpostpartum\b",
]
PAEDIATRIC_PATTERNS = [
    r"\bmy baby\b", r"\bmy toddler\b", r"\binfant\b", r"\bnewborn\b",
    r"\bmy (\d|1[0-7])[- ]year[- ]old\b", r"\bmy son\b.*\b(\d|1[0-7])\b",
    r"\bmy daughter\b.*\b(\d|1[0-7])\b", r"\bfor a child\b", r"\bkids?\b",
]

SAFETY_CATEGORIES: dict[str, tuple[list[str], str]] = {
    "medical": (
        MEDICAL_PATTERNS,
        "That sounds like something a doctor or pharmacist should look at rather "
        "than something to solve with a skincare product. Please get it checked. "
        "I can help you find products again once you've had advice.",
    ),
    "prescription": (
        PRESCRIPTION_PATTERNS,
        "Prescription treatments interact with other actives in ways I'm not able "
        "to advise on. Please ask the doctor or pharmacist who prescribed it what "
        "is safe to use alongside it.",
    ),
    "pregnancy": (
        PREGNANCY_PATTERNS,
        "Ingredient guidance during pregnancy or breastfeeding should come from a "
        "midwife, doctor or pharmacist who knows your situation — it isn't "
        "something I should advise on from a product catalogue.",
    ),
    "paediatric": (
        PAEDIATRIC_PATTERNS,
        "For a child's skin, please check with a pharmacist or GP. This catalogue "
        "is aimed at adult skincare and I don't want to guess.",
    ),
}


def check_safety(message: str) -> tuple[str, str] | None:
    """
    Return (category, safe_response) if the message must not reach the model.

    Runs first, before retrieval and before any LLM call.
    """
    text = (message or "").lower()
    for category, (patterns, response) in SAFETY_CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return category, response
    return None


# --- Claim checker ---------------------------------------------------------
# Cosmetic marketing claims are regulated. A generated sentence saying a
# cosmetic "treats" a condition can reclassify it as a medicinal claim, which
# is the difference between a deployable product and a demo. If the model
# writes one of these, we drop the sentence rather than trying to repair it.

BANNED_CLAIM_PATTERNS = [
    r"\bcures?\b", r"\btreats?\b", r"\btreatment for\b", r"\bheals?\b",
    r"\beliminates?\b", r"\bremoves? (your )?(acne|wrinkles|scars)\b",
    r"\bguaranteed\b", r"\bclinically proven\b", r"\bmedically proven\b",
    r"\bprescri", r"\bdiagnos", r"\bwill (clear|fix|cure|remove)\b",
    r"\bdermatologist[- ]recommended\b", r"\bmedical[- ]grade\b",
    r"\bsafe for (all|everyone)\b", r"\bno side effects\b", r"\bhypoallergenic\b",
]


def find_unsafe_claims(text: str) -> list[str]:
    """Return the banned phrases present in generated text."""
    found: list[str] = []
    lowered = (text or "").lower()
    for pattern in BANNED_CLAIM_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            found.append(match.group(0))
    return found


def strip_unsafe_sentences(text: str) -> tuple[str, list[str]]:
    """
    Drop any sentence containing a banned claim, keep the rest.

    Returns (cleaned_text, dropped_claims). A rising drop rate is a signal that
    the prompt has drifted and should be reviewed — worth alerting on.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text or "")
    kept, dropped = [], []
    for sentence in sentences:
        claims = find_unsafe_claims(sentence)
        if claims:
            dropped.extend(claims)
        else:
            kept.append(sentence)
    return " ".join(kept).strip(), dropped
