"""Can/hap profile önceliği testleri."""

from __future__ import annotations

from unittest.mock import patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.game_api import Profile
from diplomacy_bot.health_sync import health_dashboard_banner, work_health
from diplomacy_bot.modules import factory as factory_mod
from tests.test_modules_factory import MockApi, patch_profile


def _profile(**kw) -> Profile:
    defaults = dict(
        player_id="p1",
        username="test",
        balance=1000,
        diamonds=5000,
        xp=100,
        level=4,
        health=0,
        health_pills=100,
        onboarding_step=None,
        province_name="İsfahan",
    )
    defaults.update(kw)
    return Profile(**defaults)


def test_work_health_prefers_profile_over_auto():
    with patch("diplomacy_bot.game_api.get_profile", return_value=_profile(health=0)):
        h = work_health("tok", auto_status={"health": 100})
    assert h == 0


def test_health_dashboard_banner_can_zero_with_pills():
    msg = health_dashboard_banner({"health": 0, "pills": 10766, "pill_cooldown_ms": 0})
    assert "Can 0" in msg and "10766" in msg.replace(",", "")


def test_analyze_auto_with_profile_overrides_auto_health():
    from diplomacy_bot.health_sync import analyze_auto_with_profile

    status = {"next_work_in_ms": 0, "pill_cooldown_ms": 0, "health": 100, "health_pills": 50}
    with patch("diplomacy_bot.game_api.get_profile", return_value=_profile(health=0)):
        aa = analyze_auto_with_profile("tok", status)
    assert aa["health"] == 0


def test_analyze_auto_status_profile_health_kwarg():
    from diplomacy_bot.feature_analysis import analyze_auto_status

    status = {"next_work_in_ms": 0, "health": 100}
    aa = analyze_auto_status(status, profile_health=0)
    assert aa["health"] == 0


def test_snapshot_row_auto_uses_profile_health():
    from diplomacy_bot.readiness_probes import analyze_from_snapshot_row

    row = {
        "health": 0,
        "pills": 100,
        "diamonds": 1000,
        "work_wait_ms": 0,
        "pill_cooldown_ms": 0,
    }
    out = analyze_from_snapshot_row(row, AccountConfig("x"))
    assert out["auto"]["health"] == 0


def test_orchestrator_war_prep_uses_profile_health_for_pills():
    from diplomacy_bot.modules import orchestrator as orch

    cfg = AccountConfig(
        account_name="a1",
        role="war",
        war_enabled=True,
        training_enabled=False,
        stat_auto_enabled=False,
    )
    calls = []

    def mock_api(method, path, token, body=None, delay=0):
        calls.append(path)
        if path == "/auto/status":
            return 200, {"health": 100, "pill_cooldown_ms": 0}
        if path == "/auto/use-pills":
            return 200, {"ok": True}
        return 404, {}

    prof = _profile(health=0, health_pills=10)
    with (
        patch("diplomacy_bot.modules.orchestrator.get_profile", return_value=prof),
        patch("diplomacy_bot.game_api.get_profile", return_value=prof),
        patch("diplomacy_bot.modules.orchestrator.travel.is_traveling", return_value=False),
        patch("diplomacy_bot.modules.orchestrator.premium.fetch_premium_state", return_value={}),
        patch("diplomacy_bot.modules.orchestrator.premium.should_skip_manual_work", return_value=(True, "test")),
        patch("diplomacy_bot.modules.orchestrator.war.try_contribute", return_value=None),
        patch("diplomacy_bot.modules.orchestrator.economy.ensure_pills", return_value=None),
    ):
        orch.tick_account("tok", "a1", cfg=cfg, _api=mock_api)

    assert "/auto/use-pills" in calls


def test_premium_auto_work_note_low_health():
    from diplomacy_bot.health_sync import premium_auto_work_note

    msg = premium_auto_work_note(
        {"premium": True, "auto_work_active": True, "health": 0, "pill_cooldown_ms": 60000}
    )
    assert "Premium auto-work" in msg
    assert "Can 0/100" in msg


def test_health_dashboard_banner_pill_cooldown():
    msg = health_dashboard_banner({"health": 0, "pills": 100, "pill_cooldown_ms": 120000})
    assert "Can 0" in msg and "bekleme" in msg


def test_build_readiness_shows_can_zero_highlight():
    from diplomacy_bot.feature_analysis import build_readiness

    r = build_readiness(auto_analysis={"health": 0, "pills": 500, "pill_ready": True})
    assert any("Can 0" in h for h in r["highlights"])


def test_autofarm_premium_low_health_note():
    from diplomacy_bot.autofarm_notify import format_autofarm_success_html
    from diplomacy_bot.modules.orchestrator import TickResult

    acc = type("Acc", (), {"name": "ygt", "username": "Y.G.T"})()
    r = TickResult(account_name="ygt", username="Y.G.T", ok=True, balance_after=1000)
    r.actions = [{"skipped": "premium_auto_work", "health": 0, "pill_cooldown_ms": 120000}]
    msg = format_autofarm_success_html(acc, r)
    assert "Premium auto-work" in msg
    assert "can 0/100" in msg
    assert "hap bekleme" in msg


def test_autofarm_notify_can_restored_label():
    from diplomacy_bot.autofarm_notify import _action_labels
    from diplomacy_bot.modules.orchestrator import TickResult

    r = TickResult(account_name="a1")
    r.actions = [{"use_pills_pre": {"ok": True}}]
    labels = _action_labels(r)
    assert any("can dolduruldu" in lb for lb in labels)


def test_work_cycle_sets_used_pills_flag():
    cfg = AccountConfig(account_name="a1", work_mode="foreign")
    mock = MockApi(
        {
            ("GET", "/auto/status"): (200, {"next_work_in_ms": 0, "health": 100, "pill_cooldown_ms": 0}),
            ("GET", "/factories/work-status"): (200, {"working": False}),
            ("GET", "/factories/region"): (
                200,
                {"factories": [{"id": "dia1", "type": "elmas", "level": 10, "salary_rate": 90}]},
            ),
            ("POST", "/factories/join"): (200, {"ok": True}),
            ("POST", "/auto/use-pills"): (200, {"ok": True}),
            ("POST", "/factories/work"): (200, {"earned": {"money": 2400}}),
        }
    )
    with patch_profile(health=0, health_pills=100):
        r = factory_mod.run_work_cycle("tok", cfg, _api=mock)
    pill_calls = [c for c in mock.calls if c[1] == "/auto/use-pills"]
    assert pill_calls
    assert r.get("used_pills") is True
    assert r.get("ok") is True


def test_game_features_fetch_auto_status_uses_profile_health():
    from diplomacy_bot.game_features_health import install_game_features_health_patch
    from diplomacy_bot import game_features as gf

    gf._health_auto_patched = False
    install_game_features_health_patch()

    status = {"next_work_in_ms": 0, "health": 100, "pill_cooldown_ms": 0}
    with (
        patch("diplomacy_bot.modules.economy.get_auto_status", return_value=status),
        patch("diplomacy_bot.game_api.get_profile", return_value=_profile(health=0)),
    ):
        pack = gf.fetch_auto_status("tok")
    assert pack["analysis"]["health"] == 0
