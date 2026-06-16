#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.user_errors import (
    format_farm_preflight,
    format_hap_preflight,
    format_ms,
    format_pill_error,
    format_work_error,
)


class UserErrorsTests(unittest.TestCase):
    def test_format_ms_minutes(self):
        self.assertIn("dk", format_ms(125_000))

    def test_hap_preflight_full_health(self):
        self.assertIn("dolu", format_hap_preflight({"health": 100, "pills": 5}) or "")

    def test_hap_preflight_cooldown(self):
        msg = format_hap_preflight({"health": 50, "pills": 10, "pill_cooldown_ms": 120_000})
        self.assertIn("cooldown", (msg or "").lower())

    def test_farm_preflight_work_wait(self):
        msg = format_farm_preflight({"health": 80, "work_wait_ms": 30_000})
        self.assertIn("Work cooldown", msg or "")

    def test_pill_error_cooldown(self):
        self.assertIn("cooldown", format_pill_error({"remaining_ms": 60_000}).lower())

    def test_work_error_cooldown(self):
        self.assertIn("cooldown", format_work_error("work cooldown", cooldown_ms=45_000).lower())


if __name__ == "__main__":
    unittest.main()
