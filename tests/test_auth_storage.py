import json
import os

from bot.auth import AllowList
from bot.storage import UserPrefs


def _write(path, data, mtime):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_allow_list_reloads_on_change(tmp_path):
    path = tmp_path / "allowed_users.json"
    allow = AllowList(path)
    assert not allow.is_allowed(1)  # file missing

    _write(path, {"1": {"name": "תמיר"}}, 1000)
    assert allow.is_allowed(1)
    assert allow.name_of(1) == "תמיר"
    assert not allow.is_allowed(2)

    _write(path, {"1": {"name": "תמיר"}, "2": {"name": ""}}, 2000)
    assert allow.is_allowed(2)
    assert allow.name_of(2) is None


def test_allow_list_keeps_previous_on_invalid_json(tmp_path):
    path = tmp_path / "allowed_users.json"
    allow = AllowList(path)
    _write(path, {"1": {"name": "a"}}, 1000)
    assert allow.is_allowed(1)

    path.write_text("{ broken", encoding="utf-8")
    os.utime(path, (2000, 2000))
    assert allow.is_allowed(1)


def test_prefs_default_and_persist(tmp_path):
    path = tmp_path / "user_prefs.json"
    prefs = UserPrefs(path, "ILS")
    assert prefs.get_currency(5) == "ILS"

    prefs.set_currency(5, "USD", "Tamir")
    assert prefs.get_currency(5) == "USD"

    reloaded = UserPrefs(path, "ILS")
    assert reloaded.get_currency(5) == "USD"
    assert json.loads(path.read_text(encoding="utf-8"))["5"]["name"] == "Tamir"
    assert [p.name for p in tmp_path.iterdir()] == ["user_prefs.json"]  # no temp files left
