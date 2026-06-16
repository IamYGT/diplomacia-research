#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.ui_tracker import NAV_TRANSITION, tracker_footer, transition_text


class UiTrackerTests(unittest.TestCase):
    def test_tracker_footer(self):
        self.assertIn("cevap birazdan", tracker_footer("Hazırlanıyor"))

    def test_transition_text_known_key(self):
        text = transition_text("dash:home")
        self.assertIn("Ana sayfaya", text)
        self.assertIn("cevap birazdan", text)

    def test_transition_text_unknown_key(self):
        text = transition_text("unknown:key")
        self.assertIn("İşleniyor", text)

    def test_nav_transition_menu_keys(self):
        for key in (
            "dash:home",
            "dash:refresh",
            "menu:settings",
            "menu:fleet",
            "menu:accounts",
            "action:farm",
            "action:hap",
        ):
            self.assertIn(key, NAV_TRANSITION, f"missing {key}")


if __name__ == "__main__":
    unittest.main()
