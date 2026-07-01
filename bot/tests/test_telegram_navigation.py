#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.telegram_navigation import (
    callback_prefers_fresh_reply,
    is_navigation_callback,
    message_age_seconds,
    reply_or_edit_callback,
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
        self.assertTrue(is_navigation_callback("menu:accounts:p:1"))
        self.assertTrue(is_navigation_callback("nav:account:farm01"))
        self.assertTrue(is_navigation_callback("role:pick:farm01"))
        self.assertTrue(is_navigation_callback("fleet:menu:more"))
        self.assertTrue(is_navigation_callback("fleet:menu:main"))
        self.assertTrue(is_navigation_callback("fleet:tick:all"))
        self.assertTrue(is_navigation_callback("easy:run:farm01"))
        self.assertTrue(is_navigation_callback("mission:step:farm01"))
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


class TelegramCallbackReplyOrEditTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_callback_message_replies_with_visible_panel(self):
        now = datetime.now(timezone.utc)
        query = _Query(now - timedelta(minutes=10))
        query.message.reply_text = AsyncMock(return_value="sent")
        query.edit_message_text = AsyncMock()

        result = await reply_or_edit_callback(
            query,
            "easy:run:farm01",
            "Yeni panel",
            parse_mode="HTML",
        )

        self.assertEqual(result, "sent")
        query.message.reply_text.assert_awaited_once_with("Yeni panel", parse_mode="HTML")
        query.edit_message_text.assert_not_awaited()

    async def test_recent_callback_message_edits_in_place(self):
        now = datetime.now(timezone.utc)
        query = _Query(now - timedelta(seconds=30))
        query.message.reply_text = AsyncMock()
        query.edit_message_text = AsyncMock(return_value="edited")

        result = await reply_or_edit_callback(query, "mission:cancel", "Durdu")

        self.assertEqual(result, "edited")
        query.edit_message_text.assert_awaited_once_with("Durdu")
        query.message.reply_text.assert_not_awaited()

    async def test_fleet_more_menu_edits_recent_message(self):
        from diplomacy_bot.fleet_callbacks import open_fleet_more_menu

        now = datetime.now(timezone.utc)
        query = _Query(now - timedelta(seconds=30))
        query.message.reply_text = AsyncMock()
        query.edit_message_text = AsyncMock()

        await open_fleet_more_menu(query, "fleet:menu:more")

        query.edit_message_text.assert_awaited_once()
        query.message.reply_text.assert_not_awaited()

    async def test_fleet_more_menu_replies_for_old_message(self):
        from diplomacy_bot.fleet_callbacks import open_fleet_more_menu

        now = datetime.now(timezone.utc)
        query = _Query(now - timedelta(minutes=10))
        query.message.reply_text = AsyncMock()
        query.edit_message_text = AsyncMock()

        await open_fleet_more_menu(query, "fleet:menu:more")

        query.message.reply_text.assert_awaited_once()
        query.edit_message_text.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
