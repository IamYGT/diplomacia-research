#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.war_board import (
    analyze_wars_enriched,
    detect_player_side,
    format_war_board_html,
    power_bar,
    war_board_callback_rows,
)


SAMPLE_WAR = {
    "id": "6b37ba0f-c8eb-4129-a020-b0d8cc2de2c3",
    "status": "active",
    "war_name": None,
    "war_type": "standard",
    "attacker_name": "TÜRKELİ (İSFAHAN)",
    "defender_name": "Amacı Olmayan Devlet",
    "attacker_province": "Isfahan",
    "defender_province": "Tehran",
    "attacker_power": "1000000",
    "defender_power": "500000",
    "ends_at": "2099-01-01T00:00:00.000Z",
    "war_goals": ["fetih"],
    "is_conquest": True,
}


class WarBoardTests(unittest.TestCase):
    def test_detect_player_side_turkeli(self):
        side = detect_player_side(SAMPLE_WAR, "TÜRKELİ")
        self.assertEqual(side, "attacker")

    def test_numbered_wars(self):
        data = {"wars": [SAMPLE_WAR, {**SAMPLE_WAR, "id": "other", "war_name": "Test 2"}]}
        a = analyze_wars_enriched(data, AccountConfig("x"), player_country="TÜRKELİ")
        self.assertEqual(len(a["numbered"]), 2)
        self.assertEqual(a["numbered"][0]["index"], 1)
        self.assertTrue(a["numbered"][0]["is_player_war"])

    def test_format_has_numbers(self):
        data = {"wars": [SAMPLE_WAR]}
        a = analyze_wars_enriched(data, AccountConfig("x"), player_country="TÜRKELİ")
        html_out = format_war_board_html(data, a)
        self.assertIn("<b>1.</b>", html_out)
        self.assertIn("█", a["numbered"][0]["power_bar"])
        self.assertIn("█", html_out)

    def test_power_bar(self):
        bar, atk, defn = power_bar(750, 250)
        self.assertEqual(atk, 75)
        self.assertEqual(defn, 25)
        self.assertIn("█", bar)

    def test_callback_rows(self):
        data = {"wars": [SAMPLE_WAR]}
        a = analyze_wars_enriched(data, AccountConfig("x"))
        rows = war_board_callback_rows(a)
        self.assertTrue(any("war:pick:1" in b[1] for row in rows for b in row))


if __name__ == "__main__":
    unittest.main()
