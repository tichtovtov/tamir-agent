import json

import httpx
import pytest

from bot.ollama import OllamaClient, OllamaUnavailableError
from bot.vision import OllamaVision


def _client(handler) -> OllamaClient:
    return OllamaClient(
        "http://ollama", 5, http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def _vision(handler) -> OllamaVision:
    return OllamaVision(_client(handler), "qwen2.5vl:7b")


def _chat_reply(content: dict) -> httpx.Response:
    return httpx.Response(200, json={"message": {"content": json.dumps(content)}})


async def test_extract_price_normalizes_symbol():
    v = _vision(lambda req: _chat_reply({"amount": 9.9, "currency": "€"}))
    price = await v.extract_price(b"img")
    assert price.amount == pytest.approx(9.9)
    assert price.currency == "EUR"


async def test_extract_price_sends_image_and_schema():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return _chat_reply({"amount": 1, "currency": "USD"})

    await _vision(handler).extract_price(b"img")
    assert seen["model"] == "qwen2.5vl:7b"
    assert seen["messages"][0]["images"] == ["aW1n"]  # base64 of b"img"
    assert seen["format"]["required"] == ["amount", "currency"]


async def test_extract_price_no_amount():
    v = _vision(lambda req: _chat_reply({"amount": None, "currency": None}))
    assert await v.extract_price(b"img") is None


async def test_extract_price_amount_without_currency():
    v = _vision(lambda req: _chat_reply({"amount": 12, "currency": None}))
    price = await v.extract_price(b"img")
    assert price.amount == 12 and price.currency is None


async def test_extract_price_ollama_down():
    def handler(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(OllamaUnavailableError):
        await _vision(handler).extract_price(b"img")


async def test_check_reports_missing_models():
    c = _client(lambda req: httpx.Response(200, json={"models": [{"name": "gemma3:12b"}]}))
    problem = await c.check(["qwen2.5vl:7b", "gemma3:12b"])
    assert problem is not None and "ollama pull qwen2.5vl:7b" in problem
    assert "gemma3" not in problem


async def test_check_ok():
    c = _client(lambda req: httpx.Response(200, json={"models": [{"name": "llama3:latest"}]}))
    assert await c.check(["llama3"]) is None


async def test_check_unreachable():
    def handler(req):
        raise httpx.ConnectError("refused")

    assert "not reachable" in await _client(handler).check(["x"])
