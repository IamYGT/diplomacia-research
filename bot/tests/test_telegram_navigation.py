#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.telegram_navigation import (
    callback_prefers_fresh_reply,
    is_navigation_callback,
    message_age_seconds,
)


class _Message:
    def __init__(self, date):
        self.date = date


class _Query:
    def __init__(self, date):
        self.message = _Message(date)


class TelegramNavigationTests(unittest.TestCase):
    def test_navigation_callbacks_are_screen_openers(self):
        self.assertTrue(is_navigation_callback("dash:home"))
        self.assertTrue(is_navigation_callback("menu:fleet"))
        self.assertTrue(is_navigation_callback("nav:account:farm01"))
        self.assertFalse(is_navigation_callback("dash:refresh"))
        self.assertFalse(is_navigation_callback("farm:work"))

    def test_old_navigation_message_opens_fresh_panel(self):
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        query = _Query(now - timedelta(minutes=5))

        self.assertTrue(callback_prefers_fresh_reply("dash:home", query, now=now))

    def test_recent_navigation_message_can_be_edited(self):
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        query = _Query(now - timedelta(seconds=30))

        self.assertFalse(callback_prefers_fresh_reply("menu:settings", query, now=now))

    def test_missing_message_date_prefers_visible_panel(self):
        self.assertTrue(callback_prefers_fresh_reply("menu:accounts", _Query(None)))

    def test_action_callbacks_do_not_force_fresh_panel(self):
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        query = _Query(now - timedelta(hours=1))

        self.assertFalse(callback_prefers_fresh_reply("dash:refresh", query, now=now))

    def test_naive_datetimes_are_treated_as_utc(self):
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        age = message_age_seconds(datetime(2026, 7, 1, 11, 59), now=now)

        self.assertEqual(age, 60.0)


if __name__ == "__main__":
    unittest.main()
