"""Fleet LLM decision contract tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.adapters.deepseek_fleet_planner import plan_fleet_with_deepseek
from diplomacy_bot.domain.fleet_llm_decision import (
    build_decision_prompt,
    normalize_llm_decision,
    safe_account_summaries,
)


class FleetLlmDecisionTests(unittest.TestCase):
    def test_safe_account_summaries_drop_credentials(self):
        rows = [
            {
                "name": "u42_01",
                "province": "Tahran",
                "token": "jwt-secret",
                "jwt": "jwt-secret-2",
                "password": "secret",
                "diamonds": 120,
            }
        ]

        safe = safe_account_summaries(rows)

        self.assertEqual(safe, [{"province": "Tahran", "name": "u42_01", "diamonds": 120}])
        prompt = build_decision_prompt("Hürmüz'e çek", rows)
        self.assertNotIn("jwt-secret", prompt)
        self.assertNotIn("password", prompt)

    def test_normalize_decision_uses_allowlist_and_defaults(self):
        raw = {
            "province": "Hürmüz",
            "role": "karma",
            "vote": True,
            "province_vote": True,
            "independent_citizenship": True,
            "farm_cycles": 99,
            "actions": ["travel_to_province", "delete_account", "farm_tick", "train_hourly"],
        }

        decision = normalize_llm_decision(raw)

        self.assertEqual(decision.target.province, "Hürmüz")
        self.assertEqual(decision.target.role, "hybrid")
        self.assertTrue(decision.target.vote)
        self.assertTrue(decision.target.province_vote)
        self.assertTrue(decision.target.independent_citizenship)
        self.assertEqual(decision.target.farm_cycles, 24)
        self.assertEqual(decision.actions, ("travel_to_province", "farm_tick", "train_hourly"))
        self.assertIn("ignored_action:delete_account", decision.warnings)

    def test_deepseek_adapter_requests_json_and_normalizes_response(self):
        captured = {}

        def fake_post(url, payload, headers):
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "target": {
                                        "province": "Hürmüz",
                                        "role": "hybrid",
                                        "vote": True,
                                        "actions": ["assign_config", "farm_tick", "train_hourly"],
                                    }
                                }
                            )
                        }
                    }
                ]
            }

        decision = plan_fleet_with_deepseek(
            "20 hesabı Hürmüz'de ana fabrikaya çek, oy ver, farm yap",
            [{"name": "u1", "token": "secret-token", "province": "Tahran"}],
            _post_json=fake_post,
        )

        self.assertTrue(captured["url"].endswith("/chat/completions"))
        self.assertEqual(captured["payload"]["model"], "deepseek-v4-flash")
        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})
        self.assertNotIn("secret-token", captured["payload"]["messages"][1]["content"])
        self.assertTrue(decision.target.vote)
        self.assertEqual(decision.actions, ("assign_config", "farm_tick", "train_hourly"))


if __name__ == "__main__":
    unittest.main()
