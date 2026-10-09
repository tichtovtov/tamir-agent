import json

import httpx

from bot.nlu import Interpretation, OllamaNLU, parse_interpretation
from bot.ollama import OllamaClient


def _nlu(handler) -> OllamaNLU:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OllamaNLU(OllamaClient("http://ollama", 5, http=http), "gemma3:12b")


def _reply(**fields) -> httpx.Response:
    data = {"amount": None, "currency": None, "target_currency": None, "question": None}
    data.update(fields)
    return httpx.Response(200, json={"message": {"content": json.dumps(data)}})


async def test_interpret_sends_settings_and_history():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return _reply(action="convert", amount=90, currency="EUR")

    history = [
        {"role": "user", "content": "90"},
        {"role": "assistant", "content": "באיזה מטבע?"},
    ]
    it = await _nlu(handler).interpret("יורו", history, "ILS", None)

    assert it == Interpretation("convert", 90.0, "EUR")
    msgs = seen["messages"]
    assert msgs[0]["role"] == "system"
    assert "target currency (results are shown in it): ILS" in msgs[0]["content"]
    assert (
        "default source currency (used when a number has no currency): none" in msgs[0]["content"]
    )
    assert msgs[1:3] == history
    assert msgs[-1] == {"role": "user", "content": "יורו"}


def test_parse_clarify_with_question():
    content = json.dumps(
        {
            "action": "clarify",
            "amount": None,
            "currency": None,
            "target_currency": None,
            "question": "כמה דולר?",
        }
    )
    assert parse_interpretation(content) == Interpretation("clarify", question="כמה דולר?")


def test_parse_malformed_becomes_clarify():
    assert parse_interpretation("not json") == Interpretation("clarify")
    assert parse_interpretation('{"action": "launch_rocket"}') == Interpretation("clarify")
    assert parse_interpretation('{"action": "convert", "amount": "abc"}') == Interpretation(
        "clarify"
    )


def test_parse_empty_strings_become_none():
    content = json.dumps({"action": "set_source", "currency": "THB", "question": ""})
    assert parse_interpretation(content) == Interpretation("set_source", currency="THB")
