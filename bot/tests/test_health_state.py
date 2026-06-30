"""health_watch_state birleşik state testleri."""

import json
from pathlib import Path

import pytest

from diplomacy_bot import health_state as hs


@pytest.fixture
def tmp_data(monkeypatch, tmp_path):
    state_file = tmp_path / "health_watch_state.json"
    legacy_file = tmp_path / "pill_cd_state.json"
    monkeypatch.setattr(hs, "_STATE_FILE", state_file)
    monkeypatch.setattr(hs, "_LEGACY_PILL_FILE", legacy_file)
    return state_file, legacy_file


def test_load_save_roundtrip(tmp_data):
    state_file, _ = tmp_data
    hs.save_health_state({"ygt": {"health": 0, "pill_cooldown_ms": 120000}})
    loaded = hs.load_health_state()
    assert loaded["ygt"]["health"] == 0
    assert state_file.exists()


def test_migrate_legacy_pill_state(tmp_data):
    _, legacy_file = tmp_data
    legacy_file.write_text(json.dumps({"ygt": {"pill_cooldown_ms": 5000, "ts": 1.0}}))
    loaded = hs.load_health_state()
    assert loaded["ygt"]["pill_cooldown_ms"] == 5000


def test_update_account_row():
    state: dict = {}
    hs.update_account_row(state, "YGT", health=50, pills=10)
    row = hs.account_row(state, "ygt")
    assert row["health"] == 50
    assert row["pills"] == 10
    assert "ts" in row
