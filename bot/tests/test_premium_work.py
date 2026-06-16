"""Premium auto/work — manuel farm atlama."""

from unittest.mock import patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.game_api import Profile
from diplomacy_bot.modules import premium
from diplomacy_bot.modules.orchestrator import tick_account


def _prof(**kw):
    d = dict(
        player_id="p1",
        username="YGT",
        balance=10000,
        diamonds=100,
        xp=50,
        level=23,
        health=100,
        health_pills=50,
        onboarding_step=None,
        is_premium=True,
    )
    d.update(kw)
    return Profile(**d)


def test_should_skip_manual_work_when_premium_auto_active():
    def api(m, p, t, body=None, delay=0):
        if p == "/auto/status":
            return 200, {"auto_work_active": True, "next_work_in_ms": 0}
        if p == "/players/profile":
            return 200, {"player": {"is_premium": True, "skills": {}}}
        return 200, {}

    skip, reason = premium.should_skip_manual_work("tok", AccountConfig("x"), _api=api)
    assert skip is True
    assert reason == "premium_auto_work"


def test_tick_skips_work_for_premium_auto():
    work_called = []

    def api(m, p, t, body=None, delay=0):
        if p == "/players/passive-skills":
            return 200, {"available_points": 0, "passive_skills": {}}
        if p == "/auto/status":
            return 200, {
                "auto_work_active": True,
                "next_work_in_ms": 0,
                "free_attack_available": False,
                "health_pills": 50,
            }
        if p == "/players/profile":
            return 200, {"player": {"is_premium": True, "skills": {"kisla": 1}, "balance": 10000}}
        if p == "/factories/work":
            work_called.append(1)
        if p == "/wars/my-country":
            return 200, {"wars": []}
        return 200, {}

    cfg = AccountConfig("ygt", work_mode="own", stat_auto_enabled=False)
    with patch("diplomacy_bot.modules.orchestrator.get_profile", side_effect=[_prof(), _prof()]):
        with patch("diplomacy_bot.modules.premium.is_premium", return_value=True):
            with patch("diplomacy_bot.modules.premium.sync_premium_modes", return_value=[]):
                r = tick_account("tok", "ygt", cfg=cfg, _api=api)
    assert not work_called
    assert any(
        isinstance(a, dict) and a.get("skipped") == "premium_auto_work"
        for a in r.actions
    )
