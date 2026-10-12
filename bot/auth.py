"""Allow-list of users, read from data/allowed_users.json.

The file is edited by hand and has the form:
    {"123456789": {"name": "תמיר"}, ...}
It is re-read automatically whenever its modification time changes, so adding a
user does not require restarting the bot.

Users an admin added from Telegram (/add_user) live in a separate file written by
the bot (storage.BotUsers); the allow-list is the union of the two. When a user is
in both, the name from allowed_users.json wins.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from bot.storage import BotUsers

log = logging.getLogger(__name__)


class AllowList:
    """Read-only view of allowed_users.json (auto-reloaded) plus users added by an admin."""

    def __init__(self, path: Path, bot_users: BotUsers | None = None):
        self._path = path
        self._bot_users = bot_users
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

    def manual_users(self) -> dict[int, str]:
        """Return {user_id: name} from allowed_users.json (the hand-edited file)."""
        self._reload_if_changed()
        return dict(self._users)

    def _all(self) -> dict[int, str]:
        added = self._bot_users.all() if self._bot_users else {}
        return added | self.manual_users()

    def is_allowed(self, user_id: int) -> bool:
        """True if the user is in allowed_users.json or was added from Telegram."""
        return user_id in self._all()

    def name_of(self, user_id: int) -> str | None:
        """Return the name given to the user (None if missing or empty)."""
        return self._all().get(user_id) or None
