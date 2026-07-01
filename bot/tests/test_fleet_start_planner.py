"""Fleet start natural-language planner tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.domain.fleet_llm_decision import FleetLlmDecision, normalize_llm_decision
from diplomacy_bot.fleet_start_planner import resolve_fleet_start_plan


class FleetStartPlannerTests(unittest.TestCase):
    def test_short_command_uses_deterministic_parser(self):
        plan = resolve_fleet_start_plan(42, ["Tahran", "vote", "eyaletoy"])

        self.assertEqual(plan.source, "parser")
        self.assertEqual(plan.province, "Tahran")
        self.assertTrue(plan.opts["vote"])
        self.assertTrue(plan.opts["province_vote"])

    def test_natural_text_uses_planner_without_tokens(self):
        captured = {}
        accounts = [
            SimpleNamespace(
                name="u42_01",
                status="active",
                runtime_state="idle",
                last_balance=100,
                token="secret-token",
            )
        ]

        def fake_planner(text, summaries, fallback) -> FleetLlmDecision:
            captured["text"] = text
            captured["summaries"] = summaries
            captured["fallback"] = fallback
            return normalize_llm_decision(
                {
                    "province": "Hürmüz",
                    "role": "hybrid",
                    "vote": True,
                    "province_vote": True,
                    "independent_citizenship": True,
                },
                fallback=fallback,
            )

        with patch("diplomacy_bot.auth.scoped_list_accounts", return_value=accounts):
            plan = resolve_fleet_start_plan(
                42,
                ["20", "hesabı", "Hürmüz'e", "çek", "ana", "fabrikada", "çalıştır"],
                _planner=fake_planner,
            )

        self.assertEqual(plan.source, "deepseek")
        self.assertEqual(plan.province, "Hürmüz")
        self.assertTrue(plan.opts["vote"])
        self.assertTrue(plan.opts["province_vote"])
        self.assertTrue(plan.opts["independent_citizenship"])
        self.assertEqual(captured["summaries"], [{"name": "u42_01", "status": "active", "runtime_state": "idle", "diamonds": 100}])
        self.assertNotIn("secret-token", str(captured["summaries"]))

    def test_planner_failure_falls_back_to_parser(self):
        def broken_planner(text, summaries, fallback):
            raise RuntimeError("boom")

        plan = resolve_fleet_start_plan(
            42,
            ["Hürmüz", "vote", "hesapları", "ana", "fabrikaya", "çek"],
            _planner=broken_planner,
        )

        self.assertEqual(plan.source, "parser")
        self.assertEqual(plan.province, "Hürmüz")
        self.assertTrue(plan.opts["vote"])
        self.assertEqual(plan.warnings, ("deepseek_fallback:RuntimeError",))


if __name__ == "__main__":
    unittest.main()
