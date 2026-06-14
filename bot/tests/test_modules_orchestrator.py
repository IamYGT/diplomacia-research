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
        with patch("diplomacy_bot.modules.factory.get_profile", return_value=_prof()):
            with patch("diplomacy_bot.modules.orchestrator.get_profile", side_effect=[_prof(), _prof(balance=12400)]):
                r = tick_account("tok", "ygt", cfg=cfg, _api=api)
        self.assertTrue(r.ok)
        self.assertEqual(r.earned_money, 2400)
        self.assertEqual(r.earned_diamonds, 20)


if __name__ == "__main__":
    unittest.main()
