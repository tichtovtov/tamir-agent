"""Handler tests with stub Telegram objects (no network)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot import handlers
from bot.nlu import Interpretation
from bot.ollama import OllamaUnavailableError
from bot.parser import ParsedPrice
from bot.rates import RatesClient
from bot.storage import UserPrefs

RATES_RESPONSE = {
    "result": "success",
    "time_last_update_unix": 1760000000,
    "rates": {"USD": 1, "ILS": 3.7, "EUR": 0.9, "VND": 26000, "MXN": 18, "ARS": 1400, "THB": 33},
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
        ollama=None,
        vision=SimpleNamespace(extract_price=AsyncMock()),
        nlu=SimpleNamespace(interpret=AsyncMock()),
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


def _context(services, args=None, user_data=None):
    """Stub context. Pass the same `user_data` dict across calls to keep conversation memory."""
    file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"img")))
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"services": services}),
        args=args,
        bot=SimpleNamespace(get_file=AsyncMock(return_value=file)),
        user_data={} if user_data is None else user_data,
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


def _buttons(update) -> list[str]:
    markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    return [b.callback_data for row in markup.inline_keyboard for b in row]


async def test_from_by_country_name(services):
    await handlers.from_cmd(_update(), _context(services, ["וייטנאם"]))
    assert services.prefs.get_source(7) == "VND"


async def test_set_ambiguous_shows_buttons(services):
    u = _update()
    await handlers.set_cmd(u, _context(services, ["פסו"]))
    assert services.prefs.get_currency(7) == "ILS"  # nothing chosen yet
    # only currencies the rates provider supports are offered
    assert _buttons(u) == ["set:MXN", "set:ARS"]


async def test_set_without_args_shows_popular(services):
    u = _update()
    await handlers.set_cmd(u, _context(services))
    assert "set:USD" in _buttons(u)


async def test_from_without_args_offers_clear_when_set(services):
    services.prefs.set_source(7, "EUR")
    u = _update()
    await handlers.from_cmd(u, _context(services))
    assert "from:off" in _buttons(u)


def _button_update(data):
    query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=7, full_name="Tamir"), callback_query=query
    )


async def test_button_press_sets_currency(services):
    u = _button_update("from:VND")
    await handlers.currency_button(u, _context(services))
    assert services.prefs.get_source(7) == "VND"
    assert "דונג" in u.callback_query.edit_message_text.call_args.args[0]


async def test_button_clear_source(services):
    services.prefs.set_source(7, "EUR")
    await handlers.currency_button(_button_update("from:off"), _context(services))
    assert services.prefs.get_source(7) is None


async def test_button_rejects_unknown_code(services):
    u = _button_update("set:ZZZ")
    await handlers.currency_button(u, _context(services))
    assert services.prefs.get_currency(7) == "ILS"
    u.callback_query.edit_message_text.assert_not_called()


# --- Language-model flow ---


async def test_parsable_text_skips_language_model(services):
    await handlers.text_msg(_update("100 USD"), _context(services))
    services.nlu.interpret.assert_not_called()


async def test_unparsable_text_goes_to_language_model(services):
    services.nlu.interpret.return_value = Interpretation("convert", 30, "EUR", "USD")
    u = _update("כמה זה 30 יורו בדולרים?")
    await handlers.text_msg(u, _context(services))
    assert "33.33" in _reply_text(u)  # one-off target USD: 30 EUR = 33.33 USD
    assert services.prefs.get_currency(7) == "ILS"  # setting unchanged


async def test_clarify_then_answer_uses_history(services):
    user_data = {}
    services.nlu.interpret.return_value = Interpretation("clarify", question="כמה יורו?")
    u = _update("תמיר רוצה להמיר יורו")
    await handlers.text_msg(u, _context(services, user_data=user_data))
    assert "כמה יורו?" in _reply_text(u)

    # The bare-number answer goes to the model (not the regex path) together with the history
    services.nlu.interpret.return_value = Interpretation("convert", 90, "EUR")
    u = _update("90")
    await handlers.text_msg(u, _context(services, user_data=user_data))
    history = services.nlu.interpret.call_args.args[1]
    assert history[0] == {"role": "user", "content": "תמיר רוצה להמיר יורו"}
    assert "כמה יורו?" in history[1]["content"]
    assert "370.00" in _reply_text(u)
    assert handlers.CONVERSATION_KEY not in user_data  # cleared after success


async def test_missing_currency_question_is_remembered(services):
    user_data = {}
    await handlers.text_msg(_update("90"), _context(services, user_data=user_data))
    assert handlers.CONVERSATION_KEY in user_data

    services.nlu.interpret.return_value = Interpretation("convert", 90, "EUR")
    u = _update("יורו")
    await handlers.text_msg(u, _context(services, user_data=user_data))
    assert services.nlu.interpret.call_args.args[1][0]["content"] == "90"
    assert "370.00" in _reply_text(u)


async def test_conversation_expires(services, monkeypatch):
    user_data = {}
    await handlers.text_msg(_update("90"), _context(services, user_data=user_data))
    monkeypatch.setattr(handlers, "CONVERSATION_TTL_SECONDS", -1)
    services.nlu.interpret.return_value = Interpretation("help")
    await handlers.text_msg(_update("יורו"), _context(services, user_data=user_data))
    assert services.nlu.interpret.call_args.args[1] == []


async def test_set_source_needs_confirmation(services):
    services.nlu.interpret.return_value = Interpretation("set_source", currency="תאילנד")
    u = _update("אני בתאילנד")
    await handlers.text_msg(u, _context(services))
    assert services.prefs.get_source(7) is None  # not applied yet
    assert _buttons(u) == ["from:THB", "cancel"]

    await handlers.currency_button(_button_update("from:THB"), _context(services))
    assert services.prefs.get_source(7) == "THB"


async def test_cancel_button_changes_nothing(services):
    u = _button_update("cancel")
    await handlers.currency_button(u, _context(services))
    assert services.prefs.get_source(7) is None
    assert "לא שיניתי" in u.callback_query.edit_message_text.call_args.args[0]


async def test_clear_source_needs_confirmation(services):
    services.prefs.set_source(7, "EUR")
    services.nlu.interpret.return_value = Interpretation("clear_source")
    u = _update("חזרתי הביתה")
    await handlers.text_msg(u, _context(services))
    assert services.prefs.get_source(7) == "EUR"
    assert _buttons(u) == ["from:off", "cancel"]


async def test_unknown_currency_from_model_asks(services):
    user_data = {}
    services.nlu.interpret.return_value = Interpretation("convert", 5, "פלפלים")
    u = _update("5 פלפלים")
    await handlers.text_msg(u, _context(services, user_data=user_data))
    assert "פלפלים" in _reply_text(u)
    assert handlers.CONVERSATION_KEY in user_data


async def test_model_question_is_html_escaped(services):
    services.nlu.interpret.return_value = Interpretation("clarify", question="<b>x</b>?")
    u = _update("משהו")
    await handlers.text_msg(u, _context(services))
    assert "&lt;b&gt;" in _reply_text(u)


async def test_language_model_down_falls_back_to_help(services):
    services.nlu.interpret.side_effect = OllamaUnavailableError("down")
    u = _update("שלום")
    await handlers.text_msg(u, _context(services))
    assert "/set" in _reply_text(u)


async def test_photo_missing_currency_then_answer(services):
    user_data = {}
    services.vision.extract_price.return_value = ParsedPrice(18, None)
    await handlers.photo_msg(_update(photo=True), _context(services, user_data=user_data))

    services.nlu.interpret.return_value = Interpretation("convert", 18, "EUR")
    u = _update("יורו")
    await handlers.text_msg(u, _context(services, user_data=user_data))
    assert "74.00" in _reply_text(u)


async def test_set_target_accepts_currency_in_target_field(services):
    services.nlu.interpret.return_value = Interpretation("set_target", target_currency="EUR")
    u = _update("תעביר לי את כל התוצאות לאירו")
    await handlers.text_msg(u, _context(services))
    assert _buttons(u) == ["set:EUR", "cancel"]
