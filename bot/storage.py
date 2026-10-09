"""Per-user preferences, stored in data/user_prefs.json (written only by the bot).

Format:
    {"123456789": {"name": "Tamir Cohen", "currency": "ILS", "source": "EUR"}, ...}
`name` is the user's Telegram display name, kept for reference.
`currency` is the target currency; `source` (optional) is the currency assumed when
the user sends a bare number, e.g. the local currency while travelling.
Writes are atomic (temp file + rename) so a crash never leaves a broken file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path

log = logging.getLogger(__name__)


class UserPrefs:
    """JSON-backed store of each user's target currency."""

    def __init__(self, path: Path, default_currency: str):
        self._path = path
        self._default = default_currency
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, str]] = self._load()

    def _load(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.error("Could not parse %s (%s); starting with empty preferences", self._path, e)
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get_currency(self, user_id: int) -> str:
        """Return the user's target currency (the default if never set)."""
        return self._data.get(str(user_id), {}).get("currency", self._default)

    def set_currency(self, user_id: int, currency: str, name: str = "") -> None:
        """Set the user's target currency and persist it."""
        self._update(user_id, "currency", currency, name)

    def get_source(self, user_id: int) -> str | None:
        """Return the user's default source currency, or None if not set."""
        return self._data.get(str(user_id), {}).get("source")

    def set_source(self, user_id: int, currency: str | None, name: str = "") -> None:
        """Set (or clear, with None) the user's default source currency and persist it."""
        self._update(user_id, "source", currency, name)

    def _update(self, user_id: int, key: str, value: str | None, name: str) -> None:
        with self._lock:
            entry = self._data.setdefault(str(user_id), {})
            if value is None:
                entry.pop(key, None)
            else:
                entry[key] = value
            if name:
                entry["name"] = name
            self._save()
