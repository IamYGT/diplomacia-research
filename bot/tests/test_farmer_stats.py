"""run_quick_farm — stat otomasyonu farm ile birlikte."""

from unittest.mock import patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.farmer import run_quick_farm
from diplomacy_bot.game_api import Profile


def _prof(balance=100_000):
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


def test_quick_farm_runs_stat_automation_when_enabled():
    stat_calls = []

    def fake_stat(token, cfg, **kw):
        stat_calls.append("call")
        return {"passive": [], "upgrades": [{"ok": True, "skill": "kisla"}]}

    work = {"ok": True, "earned": {"money": 5000, "xp": 1, "diamonds": 0}, "factory_id": "f1"}

    cfg = AccountConfig("ygt", stat_auto_enabled=True)
    with patch("diplomacy_bot.farmer.get_config", return_value=cfg):
        with patch("diplomacy_bot.farmer.game_api.get_profile", return_value=_prof()):
            with patch("diplomacy_bot.modules.stats.run_stat_automation", side_effect=fake_stat):
                with patch("diplomacy_bot.modules.factory.run_work_cycle", return_value=work):
                    r = run_quick_farm("tok", "ygt")
    assert r.ok
    assert stat_calls == ["call", "call"]  # önce + farm sonrası
    assert r.actions
