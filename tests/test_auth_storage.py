import json
import os

import pytest

from bot.auth import AllowList
from bot.config import parse_ids
from bot.storage import BotUsers, UserPrefs


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


def test_prefs_source_set_and_clear(tmp_path):
    path = tmp_path / "user_prefs.json"
    prefs = UserPrefs(path, "ILS")
    assert prefs.get_source(5) is None

    prefs.set_source(5, "EUR")
    assert UserPrefs(path, "ILS").get_source(5) == "EUR"
    assert prefs.get_currency(5) == "ILS"  # target unaffected

    prefs.set_source(5, None)
    assert UserPrefs(path, "ILS").get_source(5) is None
    assert "source" not in json.loads(path.read_text(encoding="utf-8"))["5"]


def test_bot_users_add_remove_persist(tmp_path):
    path = tmp_path / "bot_users.json"
    users = BotUsers(path)
    users.add(5, "דנה", added_by=1)
    assert BotUsers(path).all() == {5: "דנה"}
    saved = json.loads(path.read_text(encoding="utf-8"))["5"]
    assert saved["added_by"] == 1 and saved["added_at"]

    assert users.remove(5)
    assert not users.remove(5)
    assert BotUsers(path).all() == {}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bot_users.json"]  # no temp files


def test_allow_list_merges_bot_users_manual_name_wins(tmp_path):
    path = tmp_path / "allowed_users.json"
    _write(path, {"1": {"name": "ידני"}}, 1000)
    bot_users = BotUsers(tmp_path / "bot_users.json")
    bot_users.add(1, "מהבוט", added_by=9)
    bot_users.add(2, "דנה", added_by=9)
    allow = AllowList(path, bot_users)

    assert allow.is_allowed(1) and allow.is_allowed(2)
    assert allow.name_of(1) == "ידני"
    assert allow.name_of(2) == "דנה"
    assert allow.manual_users() == {1: "ידני"}

    bot_users.remove(2)
    assert not allow.is_allowed(2)


def test_parse_ids():
    assert parse_ids("") == frozenset()
    assert parse_ids("123, 456 789") == frozenset({123, 456, 789})
    with pytest.raises(ValueError):
        parse_ids("123,abc")
