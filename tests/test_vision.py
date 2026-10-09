import json

import httpx
import pytest

from bot.vision import OllamaVision, VisionUnavailableError


def _vision(handler) -> OllamaVision:
    v = OllamaVision("http://ollama", "qwen2.5vl:7b", timeout=5)
    v._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return v


def _chat_reply(content: dict) -> httpx.Response:
    return httpx.Response(200, json={"message": {"content": json.dumps(content)}})


async def test_extract_price_normalizes_symbol():
    v = _vision(lambda req: _chat_reply({"amount": 9.9, "currency": "€"}))
    price = await v.extract_price(b"img")
    assert price.amount == pytest.approx(9.9)
    assert price.currency == "EUR"


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

    with pytest.raises(VisionUnavailableError):
        await _vision(handler).extract_price(b"img")


async def test_check_reports_missing_model():
    v = _vision(lambda req: httpx.Response(200, json={"models": [{"name": "llama3:latest"}]}))
    problem = await v.check()
    assert problem is not None and "ollama pull qwen2.5vl:7b" in problem


async def test_check_ok():
    v = _vision(lambda req: httpx.Response(200, json={"models": [{"name": "qwen2.5vl:7b"}]}))
    assert await v.check() is None
