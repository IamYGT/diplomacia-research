"""auto_upgrade_gold testleri."""

from unittest.mock import patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.game_api import Profile
from diplomacy_bot.modules import stats


def _prof(balance=50000):
    return Profile(
        player_id="p1",
        username="YGT",
        balance=balance,
        diamonds=10,
        xp=1,
        level=20,
        health=100,
        health_pills=5,
        onboarding_step=None,
        province_name="X",
    )


def test_run_stat_automation():
    cfg = AccountConfig("a", stat_auto_enabled=True, stat_priority=["kisla"])

    def api(method, path, token, body=None, delay=0):
        if path == "/players/passive-skills":
            return 200, {"available_points": 0, "passive_skills": {}}
        if path == "/players/profile":
            return 200, {"player": {"skills": {"kisla": 1}, "balance": 50000}}
        if path == "/players/skills/upgrade":
            return 200, {"success": True, "target_level": 2}
        return 200, {}

    with patch("diplomacy_bot.modules.stats.get_profile", return_value=_prof()):
        r = stats.run_stat_automation("tok", cfg, _api=api)
    assert len(r.get("upgrades") or []) >= 1


def test_auto_upgrade_disabled():
    cfg = AccountConfig("a", stat_auto_enabled=False)
    assert stats.auto_upgrade_gold("tok", cfg, _api=lambda *a, **k: (200, {})) == []


def test_auto_upgrade_success():
    calls = []

    def api(method, path, token, body=None, delay=0):
        calls.append((method, path, body))
        if path == "/players/profile":
            return 200, {"player": {"skills": {"kisla": 52, "bilim_insani": 1}}}
        if path == "/players/skills/upgrade":
            return 200, {"success": True, "target_level": 53}
        return 200, {}

    cfg = AccountConfig("a", stat_auto_enabled=True, stat_priority=["kisla"])
    with patch("diplomacy_bot.modules.stats.get_profile", return_value=_prof()):
        with patch("diplomacy_bot.modules.stats.get_active_skills", return_value={"kisla": 52, "bilim_insani": 1}):
            res = stats.auto_upgrade_gold("tok", cfg, max_starts=1, _api=api)
    assert len(res) == 1
    assert res[0].get("ok")


def test_run_stat_auto_now_off():
    from diplomacy_bot import game_features

    cfg = AccountConfig("ygt", stat_auto_enabled=False)
    with patch("diplomacy_bot.game_features.get_config", return_value=cfg):
        r = game_features.run_stat_auto_now("tok", "ygt")
    assert r["ok"] is False
    assert "kapalı" in (r.get("error") or "").lower()
