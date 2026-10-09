"""Parse free text like "100 USD", "$12.5", "12,50€" or "100 דולר" into amount + currency.

Rules for number formats:
- Both ',' and '.' present: the last one is the decimal separator ("1,234.56", "1.234,56").
- Only ',': a single comma followed by exactly 3 digits is a thousands separator
  ("1,299" -> 1299); otherwise it is a decimal separator ("12,5", "12,50").
- Only '.': a single dot is a decimal separator ("1.299" -> 1.299); several dots are
  thousands separators ("1.234.567").
- Apostrophes are ignored (Swiss style "1'299").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bot import currencies

# optional currency before, a number, optional currency after
_PRICE_RE = re.compile(
    r"^\s*(?P<pre>[^\d\s][^\d]*?)?\s*(?P<num>\d[\d.,']*)\s*(?P<post>[^\d].*?)?\s*$"
)


@dataclass(frozen=True)
class ParsedPrice:
    """An amount and its currency. `currency` is None when the text had only a number."""

    amount: float
    currency: str | None


def parse_number(raw: str) -> float | None:
    """Parse a number written with ',' / '.' / "'" separators. Returns None if invalid."""
    s = raw.replace("'", "").rstrip(".,")
    if not s:
        return None
    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        parts = s.split(",")
        s = s.replace(",", ".") if len(parts) == 2 and len(parts[1]) != 3 else s.replace(",", "")
    elif has_dot and s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse(text: str) -> ParsedPrice | None:
    """Parse a message into a price.

    Returns:
        ParsedPrice with currency=None if the text is just a number,
        ParsedPrice with a currency code if a currency was recognized,
        None if the text does not look like a price at all.
    """
    m = _PRICE_RE.match(text)
    if not m:
        return None
    amount = parse_number(m.group("num"))
    if amount is None:
        return None

    pre, post = m.group("pre"), m.group("post")
    if not pre and not post:
        return ParsedPrice(amount, None)

    pre_code = currencies.normalize(pre) if pre else None
    post_code = currencies.normalize(post) if post else None
    # Every non-numeric part must be a recognized currency, and they must agree
    if (pre and not pre_code) or (post and not post_code):
        return None
    if pre_code and post_code and pre_code != post_code:
        return None
    return ParsedPrice(amount, pre_code or post_code)
