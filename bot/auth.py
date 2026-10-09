"""Allow-list of users, read from data/allowed_users.json.

The file is edited by hand and has the form:
    {"123456789": {"name": "תמיר"}, ...}
It is re-read automatically whenever its modification time changes, so adding a
user does not require restarting the bot.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class AllowList:
    """Read-only view of allowed_users.json with automatic reload."""

    def __init__(self, path: Path):
        self._path = path
        self._mtime: float | None = None
        self._users: dict[int, str] = {}

    def _reload_if_changed(self) -> None:
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            if self._users:
                log.warning("%s disappeared; no users are allowed", self._path)
            self._users, self._mtime = {}, None
            return
        if mtime == self._mtime:
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._users = {int(uid): str(info.get("name", "")) for uid, info in raw.items()}
            self._mtime = mtime
            log.info("Loaded %d allowed users from %s", len(self._users), self._path)
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            # Keep the previous list so a typo while editing does not lock everyone out
            log.error("Invalid %s, keeping previous list: %s", self._path, e)

    def is_allowed(self, user_id: int) -> bool:
        self._reload_if_changed()
        return user_id in self._users

    def name_of(self, user_id: int) -> str | None:
        """Return the name given to the user in the file (None if missing or empty)."""
        self._reload_if_changed()
        return self._users.get(user_id) or None
