"""Understand free-text messages with a local Ollama language model.

Only messages the deterministic parser (parser.py) could not handle reach this
module. The model classifies the request into an `Interpretation` (convert,
change a setting, show something, or ask a clarifying question). The handler
then validates every field: currencies are resolved by our own code, and setting
changes are only applied after the user confirms with a button.

To tune understanding, edit `SYSTEM_PROMPT`; to swap the model, set
OLLAMA_TEXT_MODEL in .env.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from bot.ollama import OllamaClient

log = logging.getLogger(__name__)

ACTIONS = (
    "convert",
    "set_target",
    "set_source",
    "clear_source",
    "show_settings",
    "list_currencies",
    "help",
    "clarify",
)

SYSTEM_PROMPT = """\
You are the language-understanding component of a Telegram bot that converts prices \
between currencies. Users write in Hebrew or English. Classify the user's latest \
message and return JSON only.

The user's current settings:
- target currency (results are shown in it): {target}
- default source currency (used when a number has no currency): {source}

Actions:
- "convert": the user wants an amount converted. "amount" = the number. "currency" = \
the ISO 4217 code of the currency the amount is in, if stated or clearly implied by \
the conversation; otherwise null. If the user asks for the result in a specific \
currency just this once ("how much is 100 dollars in euros"), put its code in \
"target_currency"; otherwise null.
- "set_target": the user wants results shown in another currency from now on. \
"currency" = its ISO code.
- "set_source": the user says which currency prices will be in from now on, e.g. \
"I'm in Thailand", "I'm flying to Japan", "prices are in euro from now on". \
"currency" = its ISO code.
- "clear_source": the user wants to stop using a default source currency \
(e.g. "I'm back home", "cancel the source currency").
- "show_settings": the user asks what their settings are.
- "list_currencies": the user asks which currencies are supported or what a code is.
- "help": greetings, thanks, or messages unrelated to currency conversion.
- "clarify": the request is about money/currencies but is unclear or missing \
information you cannot infer. "question" = one short, friendly clarifying question \
in Hebrew.

Target vs. source: the target is the currency the user wants to SEE results in \
("show me prices in dollars", "convert everything to euro"); the source is the \
currency the prices they SEND are in ("I'm in Japan", "the prices here are in baht").

Rules:
- Never invent an amount. A conversion without an amount → "clarify".
- The amount is the price, never a quantity, weight or count \
("3 kg of tomatoes for 12" → amount 12).
- Magnitude suffixes multiply the amount: "k" / "אלף" = thousand, "m" / "מיליון" = \
million, "b" / "bn" / "מיליארד" = billion ("1.5k" → 1500, "2 מיליון" → 2000000).
- If only the currency of a conversion is missing, return "convert" with \
"currency": null (the bot will use the default or ask).
- Use the conversation so far: if the bot asked a question, the user's message is \
probably the answer (e.g. the bot asked which currency and the user wrote "יורו").
- Use null for every field that does not apply to the chosen action.

Examples:
- "כמה זה 30 יורו בדולרים?" → convert, amount 30, currency EUR, target_currency USD
- "אני טס מחר ליפן" → set_source, currency JPY
- "תציג לי מחירים בדולר מעכשיו" → set_target, currency USD
- "שלושה קילו עגבניות ב12" → convert, amount 12, currency null
- "כמה זה בשקלים?" (no amount anywhere in the conversation) → clarify, \
question "איזה סכום להמיר?"\
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "amount": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"]},
        "target_currency": {"type": ["string", "null"]},
        "question": {"type": ["string", "null"]},
    },
    "required": ["action", "amount", "currency", "target_currency", "question"],
}


@dataclass(frozen=True)
class Interpretation:
    """What the model understood. Currency fields are raw model output, not yet validated."""

    action: str
    amount: float | None = None
    currency: str | None = None
    target_currency: str | None = None
    question: str | None = None


class OllamaNLU:
    """Interprets free text with an Ollama language model."""

    def __init__(self, client: OllamaClient, model: str):
        self._client = client
        self._model = model

    async def interpret(
        self, text: str, history: list[dict], target: str, source: str | None
    ) -> Interpretation:
        """Interpret `text` given the recent conversation and the user's settings.

        `history` is a list of {"role": "user"|"assistant", "content": str} messages
        from the current clarification exchange (may be empty).

        Raises:
            OllamaUnavailableError: if Ollama fails.
        """
        system = SYSTEM_PROMPT.format(target=target, source=source or "none")
        messages = [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": text},
        ]
        content = await self._client.chat_json(self._model, messages, RESPONSE_SCHEMA)
        return parse_interpretation(content)


def parse_interpretation(content: str) -> Interpretation:
    """Parse the model's JSON. Anything malformed becomes a generic "clarify"."""
    try:
        data = json.loads(content)
        action = data.get("action")
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        amount = data.get("amount")
        return Interpretation(
            action=action,
            amount=float(amount) if amount is not None else None,
            currency=data.get("currency") or None,
            target_currency=data.get("target_currency") or None,
            question=data.get("question") or None,
        )
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
        log.warning("Unparsable NLU output (%s): %r", e, content)
        return Interpretation("clarify")
