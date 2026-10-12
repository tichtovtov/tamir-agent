import pytest

from bot.parser import ParsedPrice, parse, parse_number, split_magnitude


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("100", 100.0),
        ("12.5", 12.5),
        ("12,5", 12.5),
        ("12,50", 12.5),
        ("1,299", 1299.0),
        ("1,299.90", 1299.9),
        ("1.299,90", 1299.9),
        ("1.234.567", 1234567.0),
        ("1,234,567", 1234567.0),
        ("1'299", 1299.0),
        ("9.", 9.0),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("100 USD", ParsedPrice(100, "USD")),
        ("100usd", ParsedPrice(100, "USD")),
        ("usd 100", ParsedPrice(100, "USD")),
        ("$12.5", ParsedPrice(12.5, "USD")),
        ("12,50€", ParsedPrice(12.5, "EUR")),
        ("€ 25", ParsedPrice(25, "EUR")),
        ("100 דולר", ParsedPrice(100, "USD")),
        ("50 יורו", ParsedPrice(50, "EUR")),
        ('30 ש"ח', ParsedPrice(30, "ILS")),
        ("30 ₪", ParsedPrice(30, "ILS")),
        ("1,299.90 EUR", ParsedPrice(1299.9, "EUR")),
        ("  £7  ", ParsedPrice(7, "GBP")),
        ("$5 USD", ParsedPrice(5, "USD")),
        ("42", ParsedPrice(42, None)),
        # magnitude suffixes
        ("10k", ParsedPrice(10_000, None)),
        ("10K USD", ParsedPrice(10_000, "USD")),
        ("10 k usd", ParsedPrice(10_000, "USD")),
        ("$1.5m", ParsedPrice(1_500_000, "USD")),
        ("$ 3k", ParsedPrice(3_000, "USD")),
        ("2M ₪", ParsedPrice(2_000_000, "ILS")),
        ("10K€", ParsedPrice(10_000, "EUR")),
        ('1,5k ש"ח', ParsedPrice(1_500, "ILS")),
        ("2bn", ParsedPrice(2_000_000_000, None)),
        ("1b EUR", ParsedPrice(1_000_000_000, "EUR")),
        ("5 אלף דולר", ParsedPrice(5_000, "USD")),
        ("5 אלפים יורו", ParsedPrice(5_000, "EUR")),
        ("3 מיליון", ParsedPrice(3_000_000, None)),
        ("2 מיליונים ₪", ParsedPrice(2_000_000, "ILS")),
        ("1 מיליארד דולר", ParsedPrice(1_000_000_000, "USD")),
        # currency aliases that start like a suffix are not magnitudes
        ("10 kr", ParsedPrice(10, "SEK")),
        ("10kč", ParsedPrice(10, "CZK")),
        ("10mxn", ParsedPrice(10, "MXN")),
        ("5 baht", ParsedPrice(5, "THB")),
    ],
)
def test_parse_valid(text, expected):
    result = parse(text)
    assert result is not None
    assert result.amount == pytest.approx(expected.amount)
    assert result.currency == expected.currency


@pytest.mark.parametrize(
    "text",
    [
        "hello",
        "מה קורה",
        "",
        "100 dollars please",
        "$5 EUR",
        "1 2 3",
        "abc 100 def",
        "10 kg",
        "10 mm",
        "10kk",
        "5k אלף",
    ],
)
def test_parse_invalid(text):
    assert parse(text) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        (None, (1.0, None)),
        ("USD", (1.0, "USD")),
        ("k", (1_000.0, None)),
        ("k USD", (1_000.0, "USD")),
        ("M€", (1_000_000.0, "€")),
        ("kr", (1.0, "kr")),
        ("אלף דולר", (1_000.0, "דולר")),
    ],
)
def test_split_magnitude(text, expected):
    assert split_magnitude(text) == expected
