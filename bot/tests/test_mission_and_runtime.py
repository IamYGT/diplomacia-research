"""Görev, runtime hook ve katkı format testleri."""

from __future__ import annotations

from diplomacy_bot.modules.mission_types import MissionPhase, MissionPlan, MissionRuntime, PhaseSpec, PhaseStatus
from diplomacy_bot.war_contribute_format import (
    enrich_war_contribute_pack,
    format_war_contribute_html_enhanced,
    patch_war_contribute_shims,
)


def test_enrich_war_contribute_pack_adds_analysis():
    pack = {
        "ok": True,
        "side": "attacker",
        "war": {"id": "w1", "name": "Test War", "index": 2},
        "result": {"data": {"message": "ok"}},
    }
    out = enrich_war_contribute_pack(pack, "testacc")
    assert "analysis" in out
    assert out["result"]["side"] == "attacker"


def test_format_war_contribute_cooldown():
    html = format_war_contribute_html_enhanced(
        {"ok": False, "skipped": "war_cooldown", "cooldown_ms": 120_000}
    )
    assert "beklemede" in html


def test_format_war_contribute_ok_with_prep():
    html = format_war_contribute_html_enhanced(
        {
            "ok": True,
            "side": "defender",
            "prep": [{"use_pills": {"ok": True}}],
            "war": {
                "id": "w1",
                "attacker_country": "A",
                "defender_country": "B",
            },
            "result": {"data": {"message": "Vuruldu", "damage": 42}},
        }
    )
    assert "✅" in html


def test_patch_war_contribute_shims_idempotent():
    patch_war_contribute_shims()
    from diplomacy_bot import game_features

    assert getattr(game_features, "_war_ops_shim_installed", False)
    patch_war_contribute_shims()


def test_mission_plan_roundtrip_json():
    from diplomacy_bot.mission_store import _plan_from_json, _plan_to_json

    plan = MissionPlan(
        mission_id="m-1",
        account_name="ygt",
        phases=[PhaseSpec(MissionPhase.WAR_TICK, target_war_id="329")],
        war_label="Test",
        created_at=1.0,
    )
    raw = _plan_to_json(plan)
    back = _plan_from_json(raw)
    assert back.mission_id == "m-1"
    assert back.phases[0].phase == MissionPhase.WAR_TICK


def test_mission_runtime_json():
    from diplomacy_bot.mission_store import _runtime_from_json, _runtime_to_json

    plan = MissionPlan("m-1", "ygt", [PhaseSpec(MissionPhase.FARM_TICK)])
    rt = MissionRuntime("m-1", "ygt", plan, phase_status=PhaseStatus.WAITING)
    raw = _runtime_to_json(rt)
    back = _runtime_from_json(plan, raw)
    assert back.phase_status == PhaseStatus.WAITING


def test_schedule_account_falls_back_to_tick(monkeypatch):
    from diplomacy_bot.modules.mission_executor import schedule_account
    from diplomacy_bot.modules.orchestrator import TickResult

    monkeypatch.setattr(
        "diplomacy_bot.mission_store.get_active_mission",
        lambda name: None,
    )
    called = {}

    def fake_tick(token, account_name, *, cfg=None, _api=None):
        called["yes"] = account_name
        return TickResult(account_name=account_name, ok=True)

    monkeypatch.setattr(
        "diplomacy_bot.modules.mission_executor.tick_account",
        fake_tick,
    )
    r = schedule_account("tok", "ygt")
    assert called.get("yes") == "ygt"
    assert r.ok


def test_runtime_install_hooks():
    from diplomacy_bot import runtime_install

    runtime_install.install_all_runtime_hooks()
    from diplomacy_bot import telegram_ui as ui

    assert getattr(ui, "_release_badge_installed", False)
