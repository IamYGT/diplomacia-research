#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_region_mission_ui import parse_region_args


class FleetRegionMissionUiTests(unittest.TestCase):
    def test_parse_region_args_defaults_to_hurmuz(self):
        province, opts = parse_region_args([])

        self.assertEqual(province, "Hürmüz")
        self.assertFalse(opts["vote"])

    def test_parse_region_args_extracts_optional_flags(self):
        province, opts = parse_region_args(
            ["Tahran", "vote", "candidate:c1", "citizen:country-1", "visa", "country-2"]
        )

        self.assertEqual(province, "Tahran")
        self.assertTrue(opts["vote"])
        self.assertEqual(opts["candidate_id"], "c1")
        self.assertEqual(opts["citizenship_country_id"], "country-1")
        self.assertEqual(opts["visa_country_id"], "country-2")


if __name__ == "__main__":
    unittest.main()
