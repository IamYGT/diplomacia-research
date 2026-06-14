#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.game_api import Profile
from diplomacy_bot.modules import economy


def _prof(**kw) -> Profile:
    d = dict(
        player_id="p1",
        username="t",
        balance=1000,
        diamonds=5000,
        xp=0,
        level=5,
        health=100,
        health_pills=10,
        onboarding_step=None,
    )
    d.update(kw)
    return Profile(**d)


class EconomyTests(unittest.TestCase):
    def test_work_ready_false_on_cooldown(self):
        api = lambda m, p, t, body=None, delay=0: (200, {"next_work_in_ms": 120000})
        ready, wait = economy.work_ready("tok", _api=api)
        self.assertFalse(ready)
        self.assertEqual(wait, 120000)

    def test_ensure_pills_skips_when_stock_ok(self):
        api = lambda m, p, t, body=None, delay=0: (200, {"health_pills": 100, "pill_cooldown_ms": 0})
        cfg = AccountConfig(account_name="a", min_pill_stock=5)
        self.assertIsNone(economy.ensure_pills("tok", cfg, _api=api))

    def test_ensure_pills_crafts_when_low(self):
        calls = []

        def api(m, p, t, body=None, delay=0):
            calls.append((m, p, body))
            if p == "/auto/status":
                return 200, {"health_pills": 0, "pill_cooldown_ms": 0}
            if p == "/auto/craft-pills":
                return 200, {"crafted": body.get("diamonds")}
            return 404, {}

        cfg = AccountConfig(account_name="a", min_pill_stock=5, craft_diamond_batch=3000)
        with patch("diplomacy_bot.game_api.get_profile", return_value=_prof(diamonds=4000)):
            r = economy.ensure_pills("tok", cfg, _api=api)
        self.assertEqual(r.get("crafted"), 3000)


if __name__ == "__main__":
    unittest.main()
