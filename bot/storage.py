"""Files written only by the bot: per-user preferences and users added with /add_user.

data/user_prefs.json:
    {"123456789": {"name": "Tamir Cohen", "currency": "ILS", "source": "EUR"}, ...}
`name` is the user's Telegram display name, kept for reference.
`currency` is the target currency; `source` (optional) is the currency assumed when
the user sends a bare number, e.g. the local currency while travelling.

data/bot_users.json (users an admin added from Telegram):
    {"123456789": {"name": "דנה", "added_by": 111, "added_at": "2026-10-13T09:00:00+00:00"}}
It is separate from allowed_users.json, which the admin edits by hand and the bot
never writes.

Writes are atomic (temp file + rename) so a crash never leaves a broken file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


def write_json_atomic(path: Path, data: object) -> None:
    """Write `data` as JSON to `path` via a temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_json(path: Path) -> dict:
    """Read a JSON object from `path`; {} if the file is missing or broken (logged)."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.error("Could not parse %s (%s); starting empty", path, e)
        return {}


class UserPrefs:
    """JSON-backed store of each user's target currency."""

    def __init__(self, path: Path, default_currency: str):
        self._path = path
        self._default = default_currency
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, str]] = self._load()

    def _load(self) -> dict[str, dict[str, str]]:
        return _read_json(self._path)

    def _save(self) -> None:
        write_json_atomic(self._path, self._data)

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


class BotUsers:
    """JSON-backed list of users an admin added with /add_user."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, dict] = _read_json(path)

    def all(self) -> dict[int, str]:
        """Return {user_id: name} of every user added from Telegram."""
        return {int(uid): str(info.get("name", "")) for uid, info in self._data.items()}

    def add(self, user_id: int, name: str, added_by: int) -> None:
        """Add a user (or rename one already added) and persist."""
        with self._lock:
            self._data[str(user_id)] = {
                "name": name,
                "added_by": added_by,
                "added_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            write_json_atomic(self._path, self._data)

    def remove(self, user_id: int) -> bool:
        """Remove a user; returns False if they were not in the list."""
        with self._lock:
            if self._data.pop(str(user_id), None) is None:
                return False
            write_json_atomic(self._path, self._data)
            return True
