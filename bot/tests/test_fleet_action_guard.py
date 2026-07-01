#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_action_guard import is_stale_fleet_action, reject_stale_fleet_action
from diplomacy_bot.fleet_callbacks import reject_stale_fleet_command


class _Message:
    def __init__(self, date):
        self.date = date
        self.reply_text = AsyncMock()


class _Query:
    def __init__(self, date):
        self.message = _Message(date)


class FleetActionGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_old_side_effect_button(self):
        query = _Query(datetime.now(timezone.utc) - timedelta(minutes=10))

        with patch("diplomacy_bot.fleet_ui_markup.fleet_nav_inline_markup", return_value=None):
            rejected = await reject_stale_fleet_action(query, "Başlat")

        self.assertTrue(rejected)
        query.message.reply_text.assert_awaited_once()

    async def test_allows_recent_side_effect_button(self):
        query = _Query(datetime.now(timezone.utc) - timedelta(seconds=30))

        self.assertFalse(is_stale_fleet_action(query))
        rejected = await reject_stale_fleet_action(query, "Başlat")

        self.assertFalse(rejected)
        query.message.reply_text.assert_not_awaited()

    async def test_rejects_stale_more_menu_side_effect_command(self):
        query = _Query(datetime.now(timezone.utc) - timedelta(minutes=10))

        with patch("diplomacy_bot.fleet_ui_markup.fleet_nav_inline_markup", return_value=None):
            rejected = await reject_stale_fleet_command(query, "fleet:cmd:factory")

        self.assertTrue(rejected)
        query.message.reply_text.assert_awaited_once()

    async def test_allows_read_only_status_command_when_stale(self):
        query = _Query(datetime.now(timezone.utc) - timedelta(minutes=10))

        rejected = await reject_stale_fleet_command(query, "fleet:cmd:ops")

        self.assertFalse(rejected)
        query.message.reply_text.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
