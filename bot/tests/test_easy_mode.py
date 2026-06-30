"""Kolay mod — sade metin ve buton testleri."""

from __future__ import annotations

from diplomacy_bot.easy_mode import (
    EASY_MENU_LABELS,
    dashboard_headline,
    format_program_status,
    phase_label_tr,
    simplify_dashboard_html,
)
from diplomacy_bot.help_easy import format_help_easy_html
from diplomacy_bot.modules.mission_types import MissionPhase, MissionPlan, MissionRuntime, PhaseSpec


def test_phase_labels_turkish():
    assert "Savaş" in phase_label_tr("war_tick")
    assert "Fabrika" in phase_label_tr("farm_tick")


def test_program_status_no_mission():
    text = format_program_status(None, account_name="ali")
    assert "program yok" in text.lower() or "aktif program yok" in text.lower()
    assert "Savaş" in text


def test_dashboard_headline_low_health():
    h = dashboard_headline({"health": 20, "pills": 5}, autofarm=False)
    assert "Can" in h


def test_simplify_dashboard_removes_jargon():
    raw = "📌 Şimdi ne yapmalı?\nGörev: war\n⏳ API bekleme: 5s"
    out = simplify_dashboard_html(raw)
    assert "API" not in out
    assert "Sıradaki" in out


def test_easy_menu_labels_cover_keyboard():
    assert EASY_MENU_LABELS.get("⚔️ savaşa vur") == "savaşa vur"
    assert EASY_MENU_LABELS.get("▶️ programı çalıştır") == "programı çalıştır"
    assert EASY_MENU_LABELS.get("⚔️ savaş") == "war_tab"
    assert EASY_MENU_LABELS.get("🚶 seyahat") == "travel_tab"


def test_help_easy_no_slash_spam():
    text = format_help_easy_html()
    assert "/connect" in text
    assert "tek mesaj" in text.lower()
    assert "sekmeler" in text.lower()


def test_mission_runtime_status_text():
    plan = MissionPlan("m1", "ygt", [PhaseSpec(MissionPhase.WAR_TICK)], war_label="Sırbistan")
    rt = MissionRuntime("m1", "ygt", plan)
    text = format_program_status(rt)
    assert "Sırbistan" in text
    assert "mission_id" not in text.lower()
    assert "war_tick" not in text
