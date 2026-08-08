"""
Price parsing and normalisation.

WHY THIS CHANGED
----------------
The previous version returned 0.0 for anything it couldn't parse. That is a
silent commercial bug: a product with an unreadable price passed EVERY
`max_price` filter and sorted as the cheapest thing in the catalogue, so a
budget-conscious customer could be shown a "£0.00" product that isn't free.

We now return None for "we don't know". Unknown prices are excluded from
budget-filtered results and rendered as "Price unavailable" in the UI.
Not knowing is a valid state; pretending to know is not.
"""

import re


def parse_price(raw: str | float | None) -> tuple[float | None, str]:
    """Parse '£5.20' into (5.20, 'GBP'). Returns (None, currency) if unknown."""
    if raw is None:
        return None, "GBP"
    if isinstance(raw, (int, float)):
        value = float(raw)
        return (value if value > 0 else None), "GBP"

    text = str(raw).strip()
    currency = "GBP"
    if "$" in text:
        currency = "USD"
    elif "\u20ac" in text:
        currency = "EUR"
    elif "\u20b9" in text:
        currency = "INR"

    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    if match:
        try:
            value = float(match.group())
            return (value if value > 0 else None), currency
        except ValueError:
            pass
    return None, currency


def format_price(value: float | None, currency: str = "GBP") -> str:
    """Display helper — never renders a fake zero."""
    if value is None:
        return "Price unavailable"
    symbol = {"GBP": "\u00a3", "USD": "$", "EUR": "\u20ac", "INR": "\u20b9"}.get(currency, "")
    return f"{symbol}{value:,.2f}"
