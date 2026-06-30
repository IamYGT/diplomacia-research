#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import military, orchestrator, travel
from diplomacy_bot.travel_commands import format_travel_status, run_travel
from diplomacy_bot.war_ops import run_war_contribute


class MilitaryTests(unittest.TestCase):
    def test_unit_total_dict(self):
        self.assertEqual(military.unit_total({"units": {"piyade": 3, "tank": 2}}), 5)

    def test_ensure_units_skips_when_enough(self):
        def api(m, p, t, body=None, delay=0):
            return 200, {"units": {"piyade": 10}}

        cfg = AccountConfig(account_name="a", war_enabled=True)
        r = military.ensure_units_for_war("tok", cfg, _api=api)
        self.assertEqual(r.get("skipped"), "units_ok")


class WarOpsTests(unittest.TestCase):
    def test_blocks_when_traveling(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/provinces/travel/status":
                return 200, {"traveling": True, "arrived": False, "remaining_ms": 120000}
            return 200, {}

        cfg = AccountConfig(account_name="a", role="war", war_enabled=True)
        with patch("diplomacy_bot.war_ops.get_config", return_value=cfg):
            r = run_war_contribute("tok", "a", _api=api)
        self.assertEqual(r.get("skipped"), "traveling")

    def test_war_cooldown(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/auto/status":
                return 200, {"next_war_in_ms": 300000}
            if p == "/provinces/travel/status":
                return 200, {"traveling": False, "arrived": True}
            return 200, {}

        cfg = AccountConfig(account_name="a", role="war", war_enabled=True)
        with patch("diplomacy_bot.war_ops.get_config", return_value=cfg):
            r = run_war_contribute("tok", "a", _api=api)
        self.assertEqual(r.get("skipped"), "war_cooldown")

    def test_contribute_success(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/auto/status":
                return 200, {"next_war_in_ms": 0, "health": 100}
            if p == "/provinces/travel/status":
                return 200, {"traveling": False}
            if p == "/wars/my-country":
                return 200, {"wars": [{"id": "w1", "attacker_name": "A", "defender_name": "B"}]}
            if p == "/military/me":
                return 200, {"units": {"piyade": 5}}
            if p.endswith("/contribute"):
                return 200, {"ok": True}
            return 404, {}

        cfg = AccountConfig(account_name="a", role="war", war_enabled=True, contribute_side="attacker")
        with patch("diplomacy_bot.war_ops.get_config", return_value=cfg):
            with patch(
                "diplomacy_bot.war_ops.get_profile",
                return_value=type("P", (), {"country_name": "A"})(),
            ):
                r = run_war_contribute("tok", "a", _api=api)
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("side"), "attacker")


class TravelCommandsTests(unittest.TestCase):
    def test_format_idle(self):
        def api(m, p, t, body=None, delay=0):
            return 200, {"traveling": False, "arrived": True, "province_name": "Bükreş"}

        with patch("diplomacy_bot.travel_commands.get_profile", return_value=type("P", (), {"province_name": "Bükreş"})()):
            text = format_travel_status("tok", _api=api)
        self.assertIn("Bükreş", text)

    def test_run_travel_cancel(self):
        def api(m, p, t, body=None, delay=0):
            if p.endswith("/cancel"):
                return 200, {"ok": True}
            return 404, {}

        r = run_travel("tok", "iptal", _api=api)
        self.assertTrue(r.get("cancelled"))


class OrchestratorTravelSkipTests(unittest.TestCase):
    def test_skips_tick_while_traveling(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/provinces/travel/status":
                return 200, {"traveling": True, "arrived": False, "remaining_ms": 5000, "travel_destination": "Tehran"}
            return 200, {}

        cfg = AccountConfig(account_name="a", role="hybrid", war_enabled=True)
        r = orchestrator.tick_account("tok", "a", cfg=cfg, _api=api)
        self.assertIn("seyahat", (r.error or "").lower())
        self.assertTrue(any(a.get("travel") for a in r.actions if isinstance(a, dict)))


if __name__ == "__main__":
    unittest.main()
