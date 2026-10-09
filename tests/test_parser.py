import pytest

from bot.parser import ParsedPrice, parse, parse_number


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
    ],
)
def test_parse_valid(text, expected):
    result = parse(text)
    assert result is not None
    assert result.amount == pytest.approx(expected.amount)
    assert result.currency == expected.currency


@pytest.mark.parametrize(
    "text",
    ["hello", "מה קורה", "", "100 dollars please", "$5 EUR", "1 2 3", "abc 100 def"],
)
def test_parse_invalid(text):
    assert parse(text) is None
