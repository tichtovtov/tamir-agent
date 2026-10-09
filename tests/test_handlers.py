"""Handler tests with stub Telegram objects (no network)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot import handlers
from bot.parser import ParsedPrice
from bot.rates import RatesClient
from bot.storage import UserPrefs

RATES_RESPONSE = {
    "result": "success",
    "time_last_update_unix": 1760000000,
    "rates": {"USD": 1, "ILS": 3.7, "EUR": 0.9},
}


@pytest.fixture
def services(tmp_path):
    rates = RatesClient(
        3600,
        http=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=RATES_RESPONSE))
        ),
    )
    return handlers.Services(
        config=None,
        allow_list=SimpleNamespace(name_of=lambda uid: "תמיר"),
        prefs=UserPrefs(tmp_path / "user_prefs.json", "ILS"),
        rates=rates,
        vision=SimpleNamespace(extract_price=AsyncMock()),
    )


def _update(text=None, caption=None, photo=False):
    message = SimpleNamespace(
        text=text,
        caption=caption,
        photo=[SimpleNamespace(file_id="f")] if photo else None,
        reply_text=AsyncMock(),
        chat=SimpleNamespace(send_action=AsyncMock()),
    )
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=7, full_name="Tamir"), effective_message=message
    )


def _context(services, args=None):
    file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"img")))
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"services": services}),
        args=args,
        bot=SimpleNamespace(get_file=AsyncMock(return_value=file)),
    )


def _reply_text(update) -> str:
    return update.effective_message.reply_text.call_args.args[0]


async def test_bare_number_without_source_asks_for_currency(services):
    u = _update("90")
    await handlers.text_msg(u, _context(services))
    assert "/from" in _reply_text(u)


async def test_from_then_bare_number_converts(services):
    u = _update()
    await handlers.from_cmd(u, _context(services, ["יורו"]))
    assert services.prefs.get_source(7) == "EUR"

    u = _update("90")
    await handlers.text_msg(u, _context(services))
    assert "370.00" in _reply_text(u)  # 90 EUR = 100 USD = 370 ILS


async def test_explicit_currency_overrides_source(services):
    services.prefs.set_source(7, "EUR")
    u = _update("10 USD")
    await handlers.text_msg(u, _context(services))
    assert "37.00" in _reply_text(u)


async def test_from_off_clears(services):
    services.prefs.set_source(7, "EUR")
    await handlers.from_cmd(_update(), _context(services, ["off"]))
    assert services.prefs.get_source(7) is None


async def test_from_unknown_currency(services):
    u = _update()
    await handlers.from_cmd(u, _context(services, ["XYZ"]))
    assert services.prefs.get_source(7) is None
    assert "XYZ" in _reply_text(u)


async def test_photo_without_currency_uses_source(services):
    services.prefs.set_source(7, "EUR")
    services.vision.extract_price.return_value = ParsedPrice(18, None)
    u = _update(photo=True)
    await handlers.photo_msg(u, _context(services))
    assert "74.00" in _reply_text(u)


async def test_photo_detected_currency_beats_source(services):
    services.prefs.set_source(7, "EUR")
    services.vision.extract_price.return_value = ParsedPrice(10, "USD")
    u = _update(photo=True)
    await handlers.photo_msg(u, _context(services))
    assert "37.00" in _reply_text(u)
