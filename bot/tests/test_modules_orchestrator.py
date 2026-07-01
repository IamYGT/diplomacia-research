#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.game_api import Profile
from diplomacy_bot.modules.orchestrator import tick_account


def _prof(**kw) -> Profile:
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
        province_name="Bükreş",
    )
    d.update(kw)
    return Profile(**d)


class OrchestratorTests(unittest.TestCase):
    def test_tick_runs_work_and_stats(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/players/passive-skills":
                return 200, {"available_points": 0}
            if p == "/auto/status":
                return 200, {"next_work_in_ms": 0, "free_attack_available": False, "health_pills": 50}
            if p == "/wars/my-country":
                return 200, {"wars": []}
            if p == "/training-wars/my":
                return 404, {}
            if p == "/factories/work-status":
                return 200, {"working": False}
            if p == "/factories/my":
                return 200, {"factories": [{"id": "f1", "province_name": "Bükreş"}]}
            if p == "/factories/join":
                return 200, {}
            if p == "/factories/work":
                return 200, {"earned": {"money": 2400, "diamonds": 20, "xp": 17}}
            return 200, {}

        cfg = AccountConfig(account_name="ygt", work_mode="own")
        with (
            patch("diplomacy_bot.modules.factory.get_profile", return_value=_prof()),
            patch("diplomacy_bot.modules.orchestrator.get_profile", side_effect=[_prof(), _prof(balance=12400)]),
            patch("diplomacy_bot.modules.orchestrator._persist_runtime_state"),
        ):
            r = tick_account("tok", "ygt", cfg=cfg, _api=api)
        self.assertTrue(r.ok)
        self.assertEqual(r.earned_money, 2400)
        self.assertEqual(r.earned_diamonds, 20)

    def test_tick_crafts_uses_pills_then_works_when_health_empty(self):
        calls = []

        def api(m, p, t, body=None, delay=0):
            calls.append((m, p, body))
            if p == "/auto/status":
                return 200, {"next_work_in_ms": 0, "free_attack_available": False, "health_pills": 0}
            if p == "/auto/craft-pills":
                return 200, {"crafted": body.get("diamonds")}
            if p == "/auto/use-pills":
                return 200, {"ok": True}
            if p == "/factories/work-status":
                return 200, {"working": False}
            if p == "/factories/join":
                return 200, {"ok": True}
            if p == "/factories/work":
                return 200, {"earned": {"money": 2400, "diamonds": 20, "xp": 17}}
            return 200, {}

        cfg = AccountConfig(
            account_name="ygt",
            role="farm",
            work_mode="fixed",
            preferred_factory_id="factory-1",
            stat_auto_enabled=False,
            training_enabled=False,
            craft_pills_when_low=True,
            min_pill_stock=5,
            craft_diamond_batch=3000,
        )
        before = _prof(health=0, health_pills=0, diamonds=4000)
        after = _prof(balance=12400, health=100, health_pills=10, diamonds=1020)
        with (
            patch("diplomacy_bot.modules.orchestrator.get_profile", side_effect=[before, after]),
            patch("diplomacy_bot.game_api.get_profile", return_value=before),
            patch("diplomacy_bot.modules.factory.get_profile", return_value=before),
            patch("diplomacy_bot.modules.orchestrator._persist_runtime_state"),
        ):
            r = tick_account("tok", "ygt", cfg=cfg, _api=api)

        paths = [p for _, p, _ in calls]
        self.assertTrue(r.ok)
        self.assertIn({"economy": {"crafted": 3000, "data": {"crafted": 3000}}}, r.actions)
        self.assertIn({"use_pills_pre": {"ok": True, "source": "farm"}}, r.actions)
        self.assertLess(paths.index("/auto/craft-pills"), paths.index("/auto/use-pills"))
        self.assertLess(paths.index("/auto/use-pills"), paths.index("/factories/work"))


if __name__ == "__main__":
    unittest.main()
