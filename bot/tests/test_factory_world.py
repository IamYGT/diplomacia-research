"""Dünya fabrikası seçimi — /factories/world."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import factory as fac


def test_list_world_factories():
    def api(method, path, token, body=None, delay=0):
        assert path.startswith("/factories/world")
        return 200, {"factories": [{"id": "w1", "type": "elmas", "level": 5, "province_name": "Tahran"}]}

    rows = fac.list_world_factories("tok", _api=api)
    assert len(rows) == 1
    assert rows[0]["id"] == "w1"


def test_pick_world_factory_prefers_diamond():
    prof = SimpleNamespace(province_name="İstanbul")

    def api(method, path, token, body=None, delay=0):
        if path.startswith("/factories/world"):
            return 200, {
                "factories": [
                    {"id": "a", "type": "normal", "level": 1, "province_name": "A"},
                    {"id": "b", "type": "elmas", "level": 2, "province_name": "B"},
                ]
            }
        return 404, {}

    with patch.object(fac, "get_profile", return_value=prof):
        fid, prov = fac.pick_world_factory("tok", _api=api)
    assert fid == "b"
    assert prov == "B"


def test_resolve_world_mode(tmp_path, monkeypatch):
    from diplomacy_bot import store
    from diplomacy_bot.account_config import save_config

    db = tmp_path / "f.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    store.init_db()
    cfg = AccountConfig(account_name="cursor", work_mode="world", auto_travel_enabled=False)
    save_config(cfg)
    prof = SimpleNamespace(province_name="İstanbul")

    def api(method, path, token, body=None, delay=0):
        if path.startswith("/factories/world"):
            return 200, {"factories": [{"id": "w9", "type": "elmas", "level": 3, "province_name": "Tahran"}]}
        return 404, {}

    with patch.object(fac, "get_profile", return_value=prof):
        fid, err = fac.resolve_factory_id("tok", cfg, _api=api)
    assert fid == "w9"
    assert err is None
