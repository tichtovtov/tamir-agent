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

from bot import currencies
from bot.ollama import OllamaClient
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


class OllamaVision:
    """Extracts prices from images with an Ollama vision model."""

    def __init__(self, client: OllamaClient, model: str):
        self._client = client
        self._model = model

    async def extract_price(self, image: bytes) -> ParsedPrice | None:
        """Return the price found in `image`, or None if there is no recognizable amount.

        The returned currency may be None if the image shows only a number.

        Raises:
            OllamaUnavailableError: if Ollama fails.
        """
        messages = [
            {
                "role": "user",
                "content": PROMPT,
                "images": [base64.b64encode(image).decode("ascii")],
            }
        ]
        content = await self._client.chat_json(self._model, messages, RESPONSE_SCHEMA)
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
