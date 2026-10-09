import httpx
import pytest

from bot.rates import RatesClient, RatesUnavailableError, UnknownCurrencyError

RATES_RESPONSE = {
    "result": "success",
    "time_last_update_unix": 1760000000,
    "rates": {"USD": 1, "ILS": 3.7, "EUR": 0.9},
}


def _client(handler, ttl=3600) -> RatesClient:
    return RatesClient(ttl, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_convert_cross_rate():
    rates = _client(lambda req: httpx.Response(200, json=RATES_RESPONSE))
    c = await rates.convert(90, "EUR", "ILS")
    assert c.result == pytest.approx(370)
    assert c.rate == pytest.approx(3.7 / 0.9)
    assert not c.stale


async def test_unknown_currency():
    rates = _client(lambda req: httpx.Response(200, json=RATES_RESPONSE))
    with pytest.raises(UnknownCurrencyError) as e:
        await rates.convert(1, "XYZ", "ILS")
    assert e.value.code == "XYZ"


async def test_cache_used_within_ttl():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=RATES_RESPONSE)

    rates = _client(handler)
    await rates.convert(1, "USD", "ILS")
    await rates.convert(2, "USD", "EUR")
    assert len(calls) == 1


async def test_stale_cache_on_failure():
    responses = iter([httpx.Response(200, json=RATES_RESPONSE), httpx.Response(500)])
    rates = _client(lambda req: next(responses), ttl=0)
    await rates.convert(1, "USD", "ILS")
    c = await rates.convert(1, "USD", "ILS")
    assert c.stale
    assert c.result == pytest.approx(3.7)


async def test_no_rates_at_all():
    rates = _client(lambda req: httpx.Response(500))
    with pytest.raises(RatesUnavailableError):
        await rates.convert(1, "USD", "ILS")
