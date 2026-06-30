#!/usr/bin/env python3
"""event_alerts — snapshot diff olay tespit regression."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import event_alerts
from diplomacy_bot.store import Account


def _acc(name="ygt", uid=42):
    return Account(
        id=1, name=name, token="t", player_id="p", username="YGT",
        autofarm=True, last_farm_at=0, last_balance=0, proxy_id="x",
        proxy_url="", status="active", telegram_user_id=uid,
    )


class DiffEventsTests(unittest.TestCase):
    def test_no_prev_state_no_events(self):
        state = {}
        events = event_alerts.diff_events(_acc(), {"health": 100, "level": 5, "balance": 1000}, state)
        self.assertEqual(events, [])
        self.assertEqual(state["ygt"]["health"], 100)  # state kaydedildi

    def test_health_drop_triggers_attack(self):
        state = {"ygt": {"health": 90, "level": 5, "balance": 1000}}
        events = event_alerts.diff_events(_acc(), {"health": 70, "level": 5, "balance": 1000}, state)
        attacks = [e for e in events if "saldırı" in e["title"]]
        self.assertEqual(len(attacks), 1)
        self.assertIn("-20", attacks[0]["body"])

    def test_small_health_drop_no_alert(self):
        state = {"ygt": {"health": 90, "level": 5, "balance": 1000}}
        events = event_alerts.diff_events(_acc(), {"health": 85, "level": 5, "balance": 1000}, state)
        self.assertEqual(events, [])  # 5 düşüş < 10 threshold

    def test_level_up_triggers(self):
        state = {"ygt": {"health": 100, "level": 5, "balance": 1000}}
        events = event_alerts.diff_events(_acc(), {"health": 100, "level": 6, "balance": 1000}, state)
        levelups = [e for e in events if "seviye" in e["title"]]
        self.assertEqual(len(levelups), 1)

    def test_big_balance_drop_triggers(self):
        state = {"ygt": {"health": 100, "level": 5, "balance": 10000}}
        events = event_alerts.diff_events(_acc(), {"health": 100, "level": 5, "balance": 5000}, state)
        spends = [e for e in events if "harcama" in e["title"]]
        self.assertEqual(len(spends), 1)

    def test_error_snapshot_no_events(self):
        state = {"ygt": {"health": 100, "level": 5, "balance": 1000}}
        events = event_alerts.diff_events(_acc(), {"error": "api"}, state)
        self.assertEqual(events, [])

    def test_state_updates_after_diff(self):
        state = {"ygt": {"health": 90, "level": 5, "balance": 1000}}
        event_alerts.diff_events(_acc(), {"health": 70, "level": 6, "balance": 1000}, state)
        self.assertEqual(state["ygt"]["health"], 70)
        self.assertEqual(state["ygt"]["level"], 6)


if __name__ == "__main__":
    unittest.main()
