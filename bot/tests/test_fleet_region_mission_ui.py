#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_region_mission_ui import (
    format_autopilot_html,
    format_phase_plan,
    parse_region_args,
)


class FleetRegionMissionUiTests(unittest.TestCase):
    def test_parse_region_args_defaults_to_hurmuz(self):
        province, opts = parse_region_args([])

        self.assertEqual(province, "Hürmüz")
        self.assertFalse(opts["vote"])

    def test_parse_region_args_extracts_optional_flags(self):
        province, opts = parse_region_args(
            [
                "Tahran",
                "vote",
                "eyaletoy",
                "independent",
                "candidate:c1",
                "citizen:country-1",
                "visa",
                "country-2",
            ]
        )

        self.assertEqual(province, "Tahran")
        self.assertTrue(opts["vote"])
        self.assertTrue(opts["province_vote"])
        self.assertTrue(opts["independent_citizenship"])
        self.assertEqual(opts["candidate_id"], "c1")
        self.assertEqual(opts["citizenship_country_id"], "country-1")
        self.assertEqual(opts["visa_country_id"], "country-2")

    def test_format_autopilot_html_shows_repair_and_mission(self):
        result = SimpleNamespace(
            province="Hürmüz",
            inbox=SimpleNamespace(ok=2, total=2, results=[]),
            repair=SimpleNamespace(ok=20, total=20),
            mission=SimpleNamespace(
                fleet_id="region-1",
                phases=["assign_config", "travel_to_province", "residence_set", "election_vote", "farm_tick"],
                batch=SimpleNamespace(ok=20, total=20, results=[]),
            ),
        )

        text = format_autopilot_html(result)

        self.assertIn("Filo autopilot", text)
        self.assertIn("Inbox: 2/2", text)
        self.assertIn("20/20", text)
        self.assertIn("region-1", text)
        self.assertIn("hazırla → seyahat → ikamet → oy → farm", text)

    def test_format_phase_plan_uses_short_labels(self):
        plan = format_phase_plan(["travel_to_province", "residence_set", "farm_tick"])
        self.assertEqual(plan, "seyahat → ikamet → farm")

    def test_format_autopilot_html_guides_empty_fleet(self):
        result = SimpleNamespace(
            telegram_user_id=42,
            province="Hürmüz",
            inbox=SimpleNamespace(
                ok=0,
                total=1,
                results=[SimpleNamespace(ok=False, message="inbox boş")],
            ),
            repair=SimpleNamespace(ok=0, total=0),
            mission=SimpleNamespace(
                fleet_id="region-empty",
                phases=[],
                batch=SimpleNamespace(ok=0, total=0, results=[]),
            ),
        )

        text = format_autopilot_html(result)

        self.assertIn("Henüz worker yok", text)
        self.assertIn("data/token_inbox/u42_01.jwt", text)
        self.assertIn("▶️ Başlat", text)
        self.assertNotIn("Worker artık plan fazlarını", text)


if __name__ == "__main__":
    unittest.main()
