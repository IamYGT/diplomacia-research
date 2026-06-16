#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import game_features
from diplomacy_bot.response_format import (
    format_auto_status_detail,
    format_craft_result,
    format_factories_bundle,
    format_military_bundle,
    format_online_info,
    format_passive_detail,
    format_ping_result,
    format_training_bundle,
    format_war_contribute,
)


class GameFeaturesFormatTests(unittest.TestCase):
    def test_format_factories_empty(self):
        self.assertIn("Fabrikalarım", format_factories_bundle([]))

    def test_format_military_power(self):
        text = format_military_bundle({"military_power": 1200, "units": {"piyade": 5}})
        self.assertIn("1,200", text)

    def test_format_training_attack_ok(self):
        text = format_training_bundle(None, {"ok": True, "result": {"data": {"message": "Hit"}}})
        self.assertIn("Antrenman", text)

    def test_format_war_contribute_skip(self):
        text = format_war_contribute({"ok": False, "skipped": "no_active_war"})
        self.assertIn("no_active_war", text)

    def test_format_auto_status(self):
        text = format_auto_status_detail({"next_work_in_ms": 0, "free_attack_available": True})
        self.assertIn("hazır", text)

    def test_format_craft_fail(self):
        text = format_craft_result({"ok": False, "error": "Yeterli elmas yok"})
        self.assertIn("elmas", text)

    def test_format_online_count(self):
        self.assertIn("42", format_online_info({"count": 42}))

    def test_format_passive_detail(self):
        text = format_passive_detail({"available_points": 3, "passive_skills": {"güç": {"level": 2}}})
        self.assertIn("3 puan", text)

    def test_format_ping_ok(self):
        self.assertIn("OK", format_ping_result({"ok": True, "status": 200, "data": {}}))

    def test_fetch_auto_status_delegates(self):
        with patch.object(game_features.economy, "get_auto_status", return_value={"next_work_in_ms": 0}):
            r = game_features.fetch_auto_status("tok")
            self.assertTrue(r.get("ok"))
            self.assertTrue(r.get("analysis", {}).get("work_ready"))


if __name__ == "__main__":
    unittest.main()
