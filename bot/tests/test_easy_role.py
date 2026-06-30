"""Rol-aware kolay mod — farm vs war UI."""

from __future__ import annotations

from unittest.mock import patch

from diplomacy_bot.easy_mode import format_onboarding_guide_html, format_program_status, program_hub_markup
from diplomacy_bot.easy_role import war_ui_enabled
from diplomacy_bot.mission_store import enqueue_mission
from diplomacy_bot.modules.mission_types import MissionPhase


def test_war_ui_disabled_for_farm_role(tmp_path, monkeypatch):
    from diplomacy_bot import store
    from diplomacy_bot.account_config import AccountConfig, save_config

    db = tmp_path / "role.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    store.init_db()
    save_config(AccountConfig(account_name="cursor", role="farm", war_enabled=False))

    assert not war_ui_enabled("cursor")
    text = format_program_status(None, account_name="cursor")
    assert "Savaşa katılır" not in text
    assert "Fabrikada" in text


def test_program_hub_hides_war_for_farm(tmp_path, monkeypatch):
    from diplomacy_bot import store
    from diplomacy_bot.account_config import AccountConfig, save_config

    db = tmp_path / "hub.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    store.init_db()
    save_config(AccountConfig(account_name="cursor", role="farm", war_enabled=False))

    labels = [btn.text for row in program_hub_markup("cursor").inline_keyboard for btn in row]
    assert "⚔️ Savaşa Vur" not in labels
    assert "▶️ Programı Çalıştır" in labels


def test_onboarding_farm_variant():
    text = format_onboarding_guide_html(war_enabled=False)
    assert "Savaşa Vur" not in text
    assert "Fabrika" in text or "Altın" in text


def test_enqueue_mission_farm_skips_war(tmp_path, monkeypatch):
    from diplomacy_bot import store
    from diplomacy_bot.account_config import AccountConfig, save_config

    db = tmp_path / "mission.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    store.init_db()
    save_config(AccountConfig(account_name="cursor", role="farm", war_enabled=False))

    with patch("diplomacy_bot.mission_store.set_runtime_state"):
        rt = enqueue_mission("cursor")

    phases = [p.phase for p in rt.plan.phases]
    assert MissionPhase.WAR_TICK not in phases
    assert MissionPhase.FARM_TICK in phases
    assert MissionPhase.TRAIN_TICK in phases
