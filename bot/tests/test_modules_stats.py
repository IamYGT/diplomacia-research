#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.game_api import Profile
from diplomacy_bot.modules import stats


def _prof(**kw):
    d = dict(
        player_id="p",
        username="t",
        balance=0,
        diamonds=0,
        xp=0,
        level=1,
        health=100,
        health_pills=0,
        onboarding_step=None,
        player_class="kalemiye",
    )
    d.update(kw)
    return Profile(**d)


class StatsTests(unittest.TestCase):
    def test_spend_available_no_points(self):
        api = lambda m, p, t, body=None, delay=0: (200, {"available_points": 0})
        cfg = AccountConfig(account_name="a")
        self.assertEqual(stats.spend_available("tok", cfg, _api=api), [])

    def test_spend_available_uses_priority(self):
        calls = []

        def api(m, p, t, body=None, delay=0):
            if p == "/players/passive-skills":
                return 200, {"available_points": 3, "passive_skills": {"vergi_uzmani": 1}}
            if p == "/players/passive-skills/spend":
                calls.append(body)
                return 200, {"spent": body}
            return 404, {}

        cfg = AccountConfig(account_name="a", stat_priority=["vergi_uzmani", "kisla"])
        with patch("diplomacy_bot.game_api.get_profile", return_value=_prof()):
            results = stats.spend_available("tok", cfg, _api=api)
        self.assertTrue(results[0]["ok"])
        self.assertEqual(calls[0]["skill"], "vergi_uzmani")


if __name__ == "__main__":
    unittest.main()
