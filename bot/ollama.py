"""Thin async client for a local Ollama server, shared by vision.py and nlu.py."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class OllamaUnavailableError(Exception):
    """Raised when Ollama cannot be reached or returns an error."""


class OllamaClient:
    """Calls Ollama's /api/chat with structured (JSON-schema) output."""

    def __init__(self, base_url: str, timeout: float, http: httpx.AsyncClient | None = None):
        self._base_url = base_url
        self._http = http or httpx.AsyncClient(timeout=timeout)

    async def chat_json(self, model: str, messages: list[dict], schema: dict) -> str:
        """Send a chat request and return the model's raw JSON text.

        Raises:
            OllamaUnavailableError: on connection/HTTP errors or an unexpected response.
        """
        payload = {
            "model": model,
            "messages": messages,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            resp = await self._http.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise OllamaUnavailableError(str(e)) from e
        log.debug("Ollama %s raw output: %s", model, content)
        return content

    async def check(self, models: list[str]) -> str | None:
        """Verify Ollama is reachable and all `models` are pulled.

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
        missing = [m for m in models if (m if ":" in m else f"{m}:latest") not in names]
        if missing:
            return "Models not pulled: " + ", ".join(f"`ollama pull {m}`" for m in missing)
        return None

    async def aclose(self) -> None:
        await self._http.aclose()
