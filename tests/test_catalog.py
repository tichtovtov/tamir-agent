import pytest

from bot import catalog, messages


@pytest.mark.parametrize(
    "query,expected",
    [
        ("וייטנאם", ["VND"]),
        ("dong", ["VND"]),
        ("vnd", ["VND"]),
        ("פראג", ["CZK"]),
        ('ארה"ב', ["USD"]),
        ("ארה״ב", ["USD"]),
        ("פרו", ["PEN"]),  # exact keyword beats partial matches
        ("xyz", []),
        ("", []),
    ],
)
def test_search(query, expected):
    assert [c.code for c in catalog.search(query)] == expected


def test_search_ambiguous_returns_several():
    codes = {c.code for c in catalog.search("קרונה")}
    assert {"SEK", "NOK", "DKK", "ISK", "CZK"} <= codes


def test_catalog_consistency():
    codes = [c.code for c in catalog.CATALOG]
    assert len(codes) == len(set(codes))
    assert all(len(c) == 3 and c.isupper() for c in codes)
    assert all(c.region in catalog.REGIONS for c in catalog.CATALOG)
    assert set(catalog.POPULAR) <= set(codes)


def test_currency_list_fits_one_telegram_message():
    text = messages.currency_list()
    assert len(text) < 4096
    assert "<code>VND</code> דונג וייטנאמי" in text


def test_describe():
    assert catalog.describe("VND") == "🇻🇳 דונג וייטנאמי (VND)"
    assert catalog.describe("XAU") == "XAU"
