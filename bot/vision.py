"""Read a price (amount + currency) from an image using a local Ollama vision model.

The model is asked for structured JSON output (Ollama's `format` = JSON schema),
so the reply can be parsed reliably. The currency it returns is passed through
`currencies.normalize` in case the model answers with a symbol instead of a code.

To swap the model, change OLLAMA_MODEL in .env (it must be a vision-capable
model pulled with `ollama pull`). To tune recognition, edit `PROMPT`.
"""

from __future__ import annotations

import base64
import json
import logging

import httpx

from bot import currencies
from bot.parser import ParsedPrice

log = logging.getLogger(__name__)

PROMPT = (
    "You are reading a photo of a store price tag, menu, receipt or sign. "
    "Extract the single main price shown. If several prices appear, choose the most "
    "prominent final/current price (not a crossed-out old price, not a unit/per-kg price). "
    "Return the amount as a plain number (use '.' as the decimal separator, no thousands "
    "separators). Return the currency as an ISO 4217 code (e.g. USD, EUR, ILS) based on "
    "the symbol or text in the image; use null if no currency is indicated. "
    "If there is no price at all, return null for amount."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"]},
    },
    "required": ["amount", "currency"],
}


class VisionUnavailableError(Exception):
    """Raised when Ollama cannot be reached or returns an error."""


class OllamaVision:
    """Client for extracting prices from images via Ollama."""

    def __init__(self, base_url: str, model: str, timeout: float):
        self._base_url = base_url
        self._model = model
        self._http = httpx.AsyncClient(timeout=timeout)

    async def check(self) -> str | None:
        """Verify Ollama is reachable and the model is pulled.

        Returns None if all is well, or a human-readable problem description.
        """
        try:
            resp = await self._http.get(f"{self._base_url}/api/tags", timeout=5)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            return (
                f"Ollama is not reachable at {self._base_url} ({e}). "
                "Start it with `ollama serve` (or open the Ollama app)."
            )
        names = {m.get("name", "") for m in resp.json().get("models", [])}
        wanted = self._model if ":" in self._model else f"{self._model}:latest"
        if wanted not in names:
            return f"Model {self._model} is not pulled. Run: ollama pull {self._model}"
        return None

    async def extract_price(self, image: bytes) -> ParsedPrice | None:
        """Return the price found in `image`, or None if there is no recognizable amount.

        The returned currency may be None if the image shows only a number.

        Raises:
            VisionUnavailableError: if Ollama fails.
        """
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT,
                    "images": [base64.b64encode(image).decode("ascii")],
                }
            ],
            "format": RESPONSE_SCHEMA,
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            resp = await self._http.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise VisionUnavailableError(str(e)) from e

        log.debug("Vision model raw output: %s", content)
        try:
            data = json.loads(content)
            amount = data.get("amount")
            amount = float(amount) if amount is not None else None
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            log.warning("Vision model returned unparsable output: %r", content)
            return None
        if amount is None or amount <= 0:
            return None
        return ParsedPrice(amount, currencies.normalize(data.get("currency")))

    async def aclose(self) -> None:
        await self._http.aclose()
