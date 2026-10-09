"""Catalog of common currencies with Hebrew/English names, flags and countries.

Used for the /currencies list, for searching by name or country (`/set וייטנאם`),
and for the quick-pick buttons. Currencies not listed here still work by their
ISO code; to add one, append a `CurrencyInfo` to `CATALOG` (and optionally to
`POPULAR`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyInfo:
    code: str
    name_he: str
    name_en: str
    flag: str
    region: str
    keywords: tuple[str, ...] = ()  # countries/cities/nicknames for search, in Hebrew and English

    def label(self) -> str:
        """Short label for buttons, e.g. '🇻🇳 VND'."""
        return f"{self.flag} {self.code}"


MIDDLE_EAST = "ישראל והמזרח התיכון"
EUROPE = "אירופה"
ASIA = "אסיה"
AMERICAS = "אמריקה"
OCEANIA = "אוקיאניה"
AFRICA = "אפריקה"

# Display order of regions in /currencies
REGIONS = (MIDDLE_EAST, EUROPE, ASIA, AMERICAS, OCEANIA, AFRICA)


def _c(code, he, en, flag, region, *keywords) -> CurrencyInfo:
    return CurrencyInfo(code, he, en, flag, region, keywords)


CATALOG: tuple[CurrencyInfo, ...] = (
    # Israel & Middle East
    _c("ILS", "שקל חדש", "Israeli New Shekel", "🇮🇱", MIDDLE_EAST, "ישראל", "israel"),
    _c("JOD", "דינר ירדני", "Jordanian Dinar", "🇯🇴", MIDDLE_EAST, "ירדן", "jordan", "פטרה"),
    _c("EGP", "לירה מצרית", "Egyptian Pound", "🇪🇬", MIDDLE_EAST, "מצרים", "egypt", "סיני"),
    _c(
        "AED",
        "דירהם אמירתי",
        "UAE Dirham",
        "🇦🇪",
        MIDDLE_EAST,
        "איחוד האמירויות",
        "אמירויות",
        "דובאי",
        "אבו דאבי",
        "uae",
        "dubai",
        "emirates",
    ),
    _c("TRY", "לירה טורקית", "Turkish Lira", "🇹🇷", MIDDLE_EAST, "טורקיה", "turkey", "איסטנבול"),
    # Europe
    _c(
        "EUR",
        "יורו",
        "Euro",
        "🇪🇺",
        EUROPE,
        "אירופה",
        "europe",
        "גרמניה",
        "צרפת",
        "איטליה",
        "ספרד",
        "יוון",
        "הולנד",
        "פורטוגל",
        "אוסטריה",
        "בלגיה",
        "אירלנד",
        "פינלנד",
        "קרואטיה",
        "קפריסין",
        "בולגריה",
        "מונטנגרו",
        "germany",
        "france",
        "italy",
        "spain",
        "greece",
        "netherlands",
        "portugal",
        "austria",
        "belgium",
        "ireland",
        "finland",
        "croatia",
        "cyprus",
        "bulgaria",
        "montenegro",
    ),
    _c(
        "GBP",
        "לירה שטרלינג",
        "British Pound",
        "🇬🇧",
        EUROPE,
        "בריטניה",
        "אנגליה",
        "לונדון",
        "סקוטלנד",
        "uk",
        "britain",
        "england",
        "london",
        "scotland",
    ),
    _c("CHF", "פרנק שווייצרי", "Swiss Franc", "🇨🇭", EUROPE, "שווייץ", "שוויץ", "switzerland"),
    _c(
        "CZK",
        "קורונה צ'כית",
        "Czech Koruna",
        "🇨🇿",
        EUROPE,
        "צ'כיה",
        "פראג",
        "קרונה צ'כית",
        "czech",
        "prague",
    ),
    _c(
        "HUF",
        "פורינט הונגרי",
        "Hungarian Forint",
        "🇭🇺",
        EUROPE,
        "הונגריה",
        "בודפשט",
        "hungary",
        "budapest",
    ),
    _c("PLN", "זלוטי פולני", "Polish Zloty", "🇵🇱", EUROPE, "פולין", "ורשה", "קרקוב", "poland"),
    _c("RON", "לאו רומני", "Romanian Leu", "🇷🇴", EUROPE, "רומניה", "בוקרשט", "romania"),
    _c("RSD", "דינר סרבי", "Serbian Dinar", "🇷🇸", EUROPE, "סרביה", "בלגרד", "serbia"),
    _c(
        "GEL",
        "לארי גאורגי",
        "Georgian Lari",
        "🇬🇪",
        EUROPE,
        "גאורגיה",
        "גרוזיה",
        "טביליסי",
        "בטומי",
        "georgia",
        "tbilisi",
        "batumi",
    ),
    _c(
        "AZN",
        "מנאט אזרבייג'ני",
        "Azerbaijani Manat",
        "🇦🇿",
        EUROPE,
        "אזרבייג'ן",
        "באקו",
        "azerbaijan",
        "baku",
    ),
    _c("SEK", "קרונה שוודית", "Swedish Krona", "🇸🇪", EUROPE, "שוודיה", "sweden"),
    _c("NOK", "קרונה נורווגית", "Norwegian Krone", "🇳🇴", EUROPE, "נורווגיה", "norway"),
    _c("DKK", "קרונה דנית", "Danish Krone", "🇩🇰", EUROPE, "דנמרק", "קופנהגן", "denmark"),
    _c("ISK", "קרונה איסלנדית", "Icelandic Krona", "🇮🇸", EUROPE, "איסלנד", "iceland"),
    _c("UAH", "הריבניה אוקראינית", "Ukrainian Hryvnia", "🇺🇦", EUROPE, "אוקראינה", "ukraine"),
    _c("RUB", "רובל רוסי", "Russian Ruble", "🇷🇺", EUROPE, "רוסיה", "russia"),
    # Asia
    _c("THB", "באט תאילנדי", "Thai Baht", "🇹🇭", ASIA, "תאילנד", "בנגקוק", "thailand"),
    _c("VND", "דונג וייטנאמי", "Vietnamese Dong", "🇻🇳", ASIA, "וייטנאם", "ויטנאם", "vietnam"),
    _c("JPY", "ין יפני", "Japanese Yen", "🇯🇵", ASIA, "יפן", "טוקיו", "japan", "tokyo"),
    _c("CNY", "יואן סיני", "Chinese Yuan", "🇨🇳", ASIA, "סין", "china", "renminbi", "rmb"),
    _c("HKD", "דולר הונג קונגי", "Hong Kong Dollar", "🇭🇰", ASIA, "הונג קונג", "hong kong"),
    _c("TWD", "דולר טאיוואני", "New Taiwan Dollar", "🇹🇼", ASIA, "טאיוואן", "taiwan"),
    _c("KRW", "וון דרום קוריאני", "South Korean Won", "🇰🇷", ASIA, "קוריאה", "סיאול", "korea"),
    _c("SGD", "דולר סינגפורי", "Singapore Dollar", "🇸🇬", ASIA, "סינגפור", "singapore"),
    _c("MYR", "רינגיט מלזי", "Malaysian Ringgit", "🇲🇾", ASIA, "מלזיה", "malaysia"),
    _c(
        "IDR",
        "רופיה אינדונזית",
        "Indonesian Rupiah",
        "🇮🇩",
        ASIA,
        "אינדונזיה",
        "באלי",
        "indonesia",
        "bali",
    ),
    _c("PHP", "פסו פיליפיני", "Philippine Peso", "🇵🇭", ASIA, "פיליפינים", "philippines"),
    _c("KHR", "ריאל קמבודי", "Cambodian Riel", "🇰🇭", ASIA, "קמבודיה", "cambodia"),
    _c("LAK", "קיפ לאי", "Lao Kip", "🇱🇦", ASIA, "לאוס", "laos"),
    _c("INR", "רופי הודי", "Indian Rupee", "🇮🇳", ASIA, "הודו", "india", "גואה"),
    _c("NPR", "רופי נפאלי", "Nepalese Rupee", "🇳🇵", ASIA, "נפאל", "nepal"),
    _c("LKR", "רופי סרי לנקי", "Sri Lankan Rupee", "🇱🇰", ASIA, "סרי לנקה", "sri lanka"),
    # Americas
    _c(
        "USD",
        "דולר אמריקאי",
        "US Dollar",
        "🇺🇸",
        AMERICAS,
        "ארצות הברית",
        'ארה"ב',
        "ארה״ב",
        "אמריקה",
        "usa",
        "united states",
        "america",
    ),
    _c("CAD", "דולר קנדי", "Canadian Dollar", "🇨🇦", AMERICAS, "קנדה", "canada"),
    _c("MXN", "פסו מקסיקני", "Mexican Peso", "🇲🇽", AMERICAS, "מקסיקו", "mexico"),
    _c("BRL", "ריאל ברזילאי", "Brazilian Real", "🇧🇷", AMERICAS, "ברזיל", "brazil"),
    _c("ARS", "פסו ארגנטינאי", "Argentine Peso", "🇦🇷", AMERICAS, "ארגנטינה", "argentina"),
    _c("CLP", "פסו צ'יליאני", "Chilean Peso", "🇨🇱", AMERICAS, "צ'ילה", "chile"),
    _c("COP", "פסו קולומביאני", "Colombian Peso", "🇨🇴", AMERICAS, "קולומביה", "colombia"),
    _c("PEN", "סול פרואני", "Peruvian Sol", "🇵🇪", AMERICAS, "פרו", "peru"),
    _c("CRC", "קולון קוסטה ריקני", "Costa Rican Colon", "🇨🇷", AMERICAS, "קוסטה ריקה", "costa rica"),
    # Oceania
    _c("AUD", "דולר אוסטרלי", "Australian Dollar", "🇦🇺", OCEANIA, "אוסטרליה", "australia"),
    _c("NZD", "דולר ניו זילנדי", "New Zealand Dollar", "🇳🇿", OCEANIA, "ניו זילנד", "new zealand"),
    # Africa
    _c("MAD", "דירהם מרוקאי", "Moroccan Dirham", "🇲🇦", AFRICA, "מרוקו", "morocco"),
    _c(
        "ZAR",
        "ראנד דרום אפריקאי",
        "South African Rand",
        "🇿🇦",
        AFRICA,
        "דרום אפריקה",
        "south africa",
    ),
    _c("KES", "שילינג קנייתי", "Kenyan Shilling", "🇰🇪", AFRICA, "קניה", "kenya"),
    _c(
        "TZS",
        "שילינג טנזני",
        "Tanzanian Shilling",
        "🇹🇿",
        AFRICA,
        "טנזניה",
        "זנזיבר",
        "tanzania",
        "zanzibar",
    ),
    _c("ETB", "ביר אתיופי", "Ethiopian Birr", "🇪🇹", AFRICA, "אתיופיה", "ethiopia"),
)

BY_CODE: dict[str, CurrencyInfo] = {c.code: c for c in CATALOG}

# Shown as quick-pick buttons for /set and /from without arguments
POPULAR: tuple[str, ...] = (
    "ILS", "USD", "EUR", "GBP",
    "THB", "VND", "JPY", "GEL",
    "TRY", "CZK", "HUF", "CHF",
)  # fmt: skip


def _norm(s: str) -> str:
    return s.strip().casefold().replace("״", '"').replace("׳", "'")


def search(query: str) -> list[CurrencyInfo]:
    """Find catalog currencies whose code, names or keywords contain `query`.

    Exact matches (code, a full name or a keyword) win over partial ones, so
    "פרו" finds Peru and not every word containing those letters.
    """
    q = _norm(query)
    if not q:
        return []
    exact, partial = [], []
    for c in CATALOG:
        fields = [_norm(f) for f in (c.code, c.name_he, c.name_en, *c.keywords)]
        if q in fields:
            exact.append(c)
        elif any(q in f for f in fields):
            partial.append(c)
    return exact or partial


def describe(code: str) -> str:
    """Human-readable name like '🇻🇳 דונג וייטנאמי (VND)', or just the code if unknown."""
    c = BY_CODE.get(code)
    return f"{c.flag} {c.name_he} ({code})" if c else code
