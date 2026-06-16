#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.feature_analysis import (
    analyze_quests,
    analyze_wars,
    build_readiness,
)


class FeatureAnalysisTests(unittest.TestCase):
    def test_analyze_quests_claimable(self):
        quests = [
            {"quest_key": "a", "progress": 1, "target": 1, "rewarded": False, "reward": {"money": 5000}},
            {"quest_key": "b", "progress": 0, "target": 3, "rewarded": False, "reward": {"money": 1000}},
        ]
        a = analyze_quests(quests)
        self.assertEqual(a["claimable_count"], 1)
        self.assertEqual(a["pending_money"], 5000)

    def test_analyze_wars_active(self):
        data = {"wars": [{"id": "1", "status": "active", "war_name": "Test"}]}
        wa = analyze_wars(data)
        self.assertEqual(wa["war_count"], 1)

    def test_build_readiness(self):
        r = build_readiness(
            quests_analysis={"claimable_count": 2, "pending_money": 10000},
            auto_analysis={"work_ready": True},
        )
        self.assertTrue(r["work_ready"])
        self.assertEqual(r["quest_claimable"], 2)
        self.assertGreaterEqual(len(r["highlights"]), 2)


if __name__ == "__main__":
    unittest.main()
