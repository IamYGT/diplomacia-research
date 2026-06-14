#!/usr/bin/env python3
"""Koç inline buton sıralama testleri."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.game_api import Profile
from diplomacy_bot.game_coach import coach_action_buttons


def _p(**kw) -> Profile:
    defaults = dict(
        player_id="p1",
        username="t",
        balance=0,
        diamonds=0,
        xp=0,
        level=4,
        health=100,
        health_pills=0,
        onboarding_step=None,
    )
    defaults.update(kw)
    return Profile(**defaults)


class CoachButtonTests(unittest.TestCase):
    def _labels(self, profile, topic):
        btns = coach_action_buttons(profile, topic)
        self.assertIsNotNone(btns)
        return [label for label, _ in btns[0]]

    def test_health_zero_hap_first(self):
        labels = self._labels(_p(health=0, health_pills=3), "fabrika")
        self.assertEqual(labels[0], "💊 Hap kullan")

    def test_can_topic_hap_before_farm(self):
        labels = self._labels(_p(health=30, health_pills=2), "can")
        self.assertEqual(labels[0], "💊 Hap kullan")
        self.assertIn("🌾 Farm yap", labels)

    def test_gorev_topic_quests_before_farm_when_healthy(self):
        labels = self._labels(_p(health=100, health_pills=0), "görev")
        self.assertEqual(labels[0], "🎁 Görev topla")

    def test_no_buttons_without_pills_and_wrong_topic(self):
        btns = coach_action_buttons(_p(health=50, health_pills=0), "savaş")
        self.assertIsNone(btns)


if __name__ == "__main__":
    unittest.main()
