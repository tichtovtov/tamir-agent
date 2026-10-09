"""Currency symbols, aliases and display helpers.

To support a new way of writing a currency (e.g. a nickname in Hebrew), add it to
`ALIASES`. Keys are matched case-insensitively. Any 3-letter ISO 4217 code is
accepted as-is, so codes do not need to be listed here.
"""

from __future__ import annotations

import re

# alias (lowercase) -> ISO 4217 code
ALIASES: dict[str, str] = {
    # Symbols
    "$": "USD",
    "us$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₪": "ILS",
    "¥": "JPY",
    "₩": "KRW",
    "₹": "INR",
    "₽": "RUB",
    "₺": "TRY",
    "฿": "THB",
    "₫": "VND",
    "zł": "PLN",
    "kč": "CZK",
    "chf": "CHF",
    # Hebrew
    "דולר": "USD",
    "דולרים": "USD",
    "יורו": "EUR",
    "שקל": "ILS",
    "שקלים": "ILS",
    'ש"ח': "ILS",
    "ש״ח": "ILS",
    "שח": "ILS",
    "ליש״ט": "GBP",
    'ליש"ט': "GBP",
    "פאונד": "GBP",
    "לירה שטרלינג": "GBP",
    "ין": "JPY",
    "פרנק": "CHF",
    "רובל": "RUB",
    "לירה טורקית": "TRY",
    "באט": "THB",
    "זלוטי": "PLN",
    "דונג": "VND",
    "וון": "KRW",
    "יואן": "CNY",
    "רופיה": "IDR",
    "רינגיט": "MYR",
    "פורינט": "HUF",
    "לארי": "GEL",
    # English names / common non-ISO abbreviations
    "nis": "ILS",
    "shekel": "ILS",
    "shekels": "ILS",
    "dollar": "USD",
    "dollars": "USD",
    "euro": "EUR",
    "euros": "EUR",
    "pound": "GBP",
    "pounds": "GBP",
    "yen": "JPY",
    "baht": "THB",
    "lira": "TRY",
    "tl": "TRY",
    "kr": "SEK",
    "lei": "RON",
    "dong": "VND",
    "won": "KRW",
    "yuan": "CNY",
    "rmb": "CNY",
    "rupiah": "IDR",
    "ringgit": "MYR",
    "forint": "HUF",
    "lari": "GEL",
    "zloty": "PLN",
    "koruna": "CZK",
    "rand": "ZAR",
}

# ISO code -> symbol used when displaying results (falls back to the code itself)
DISPLAY_SYMBOLS: dict[str, str] = {
    "ILS": "₪",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}

_ISO_RE = re.compile(r"^[A-Za-z]{3}$")


def normalize(token: str | None) -> str | None:
    """Convert a symbol, alias or ISO code to an upper-case ISO code.

    Returns None if the token is not recognized. Note that a 3-letter token is
    returned as an ISO code even if no such currency exists; callers validate it
    against the list of currencies the rates provider supports.
    """
    if not token:
        return None
    t = token.strip().lower()
    if t in ALIASES:
        return ALIASES[t]
    if _ISO_RE.match(t):
        return t.upper()
    return None


def symbol(code: str) -> str:
    """Return the display symbol for an ISO code (or the code itself)."""
    return DISPLAY_SYMBOLS.get(code, code)


def format_amount(amount: float, code: str) -> str:
    """Format an amount with thousands separators and its currency, e.g. '1,234.50 ₪'."""
    return f"{amount:,.2f} {symbol(code)}"
