#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _TgObj:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _TgButton:
    def __init__(self, text, callback_data=None, **kwargs):
        self.text = text
        self.callback_data = callback_data
        self.kwargs = kwargs


class _TgMarkup:
    def __init__(self, inline_keyboard):
        self.inline_keyboard = inline_keyboard


if "telegram" not in sys.modules:
    telegram_stub = ModuleType("telegram")
    sys.modules["telegram"] = telegram_stub
telegram_stub = sys.modules["telegram"]
telegram_stub.Bot = getattr(telegram_stub, "Bot", _TgObj)
telegram_stub.BotCommand = getattr(telegram_stub, "BotCommand", _TgObj)
telegram_stub.InlineKeyboardButton = getattr(telegram_stub, "InlineKeyboardButton", _TgButton)
telegram_stub.InlineKeyboardMarkup = getattr(telegram_stub, "InlineKeyboardMarkup", _TgMarkup)
telegram_stub.KeyboardButton = getattr(telegram_stub, "KeyboardButton", _TgObj)
telegram_stub.MenuButtonCommands = getattr(telegram_stub, "MenuButtonCommands", _TgObj)
telegram_stub.ReplyKeyboardMarkup = getattr(telegram_stub, "ReplyKeyboardMarkup", _TgObj)
telegram_stub.Update = getattr(telegram_stub, "Update", _TgObj)
if "telegram.ext" not in sys.modules:
    ext_stub = ModuleType("telegram.ext")
    sys.modules["telegram.ext"] = ext_stub
ext_stub = sys.modules["telegram.ext"]
ext_stub.Application = getattr(ext_stub, "Application", MagicMock)
ext_stub.CallbackQueryHandler = getattr(ext_stub, "CallbackQueryHandler", MagicMock)
ext_stub.CommandHandler = getattr(ext_stub, "CommandHandler", MagicMock)
ext_stub.ContextTypes = getattr(ext_stub, "ContextTypes", MagicMock)
ext_stub.MessageHandler = getattr(ext_stub, "MessageHandler", MagicMock)
ext_stub.filters = getattr(ext_stub, "filters", MagicMock)
if "telegram.constants" not in sys.modules:
    constants_stub = ModuleType("telegram.constants")
    sys.modules["telegram.constants"] = constants_stub
constants_stub = sys.modules["telegram.constants"]
constants_stub.ChatAction = getattr(constants_stub, "ChatAction", MagicMock)
if "telegram.error" not in sys.modules:
    error_stub = ModuleType("telegram.error")
    sys.modules["telegram.error"] = error_stub
error_stub = sys.modules["telegram.error"]
error_stub.BadRequest = getattr(error_stub, "BadRequest", Exception)
error_stub.Conflict = getattr(error_stub, "Conflict", Exception)

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

        with (
            patch("diplomacy_bot.fleet_ui_markup.fleet_nav_inline_markup", return_value=None),
            patch("diplomacy_bot.fleet_status.format_fleet_ops_status", return_value="<b>durum</b>") as status,
        ):
            rejected = await reject_stale_fleet_action(query, "Başlat", 42)

        self.assertTrue(rejected)
        status.assert_called_once_with(42, detailed=False)
        query.message.reply_text.assert_awaited_once()
        text = query.message.reply_text.call_args.args[0]
        self.assertIn("Eski <b>Başlat</b> butonu", text)
        self.assertIn("<b>durum</b>", text)

    async def test_allows_recent_side_effect_button(self):
        query = _Query(datetime.now(timezone.utc) - timedelta(seconds=30))

        self.assertFalse(is_stale_fleet_action(query))
        rejected = await reject_stale_fleet_action(query, "Başlat")

        self.assertFalse(rejected)
        query.message.reply_text.assert_not_awaited()

    async def test_rejects_stale_more_menu_side_effect_command(self):
        query = _Query(datetime.now(timezone.utc) - timedelta(minutes=10))

        with patch("diplomacy_bot.fleet_ui_markup.fleet_nav_inline_markup", return_value=None):
            rejected = await reject_stale_fleet_command(query, "fleet:cmd:factory", 99)

        self.assertTrue(rejected)
        query.message.reply_text.assert_awaited_once()

    async def test_allows_read_only_status_command_when_stale(self):
        query = _Query(datetime.now(timezone.utc) - timedelta(minutes=10))

        rejected = await reject_stale_fleet_command(query, "fleet:cmd:ops")

        self.assertFalse(rejected)
        query.message.reply_text.assert_not_awaited()

    async def test_token_inbox_callback_runs_autopilot(self):
        from diplomacy_bot import callbacks as cb
        from diplomacy_bot.fleet_callbacks import install_fleet_command_callbacks

        original = cb.handle_callback
        old_flag = getattr(cb, "_fleet_cmd_callbacks_installed", False)
        cb._fleet_cmd_callbacks_installed = False
        install_fleet_command_callbacks()
        try:
            query = _Query(datetime.now(timezone.utc))
            result = MagicMock()
            with (
                patch(
                    "diplomacy_bot.fleet_mission_service.start_fleet_autopilot_for_uid",
                    return_value=result,
                ) as start,
                patch("diplomacy_bot.fleet_region_mission_ui.format_autopilot_html", return_value="<b>ok</b>"),
                patch("diplomacy_bot.fleet_callbacks.fleet_nav_inline_markup", return_value=None),
            ):
                await cb.handle_callback(None, None, "fleet:cmd:inbox", None, query, 99)
            start.assert_called_once_with(99)
            query.message.reply_text.assert_awaited_once()
            self.assertEqual(query.message.reply_text.call_args.args[0], "<b>ok</b>")
        finally:
            cb.handle_callback = original
            cb._fleet_cmd_callbacks_installed = old_flag

    async def test_rejects_stale_region_side_effect_commands(self):
        from diplomacy_bot import callbacks as cb
        from diplomacy_bot.fleet_region_hooks import patch_fleet_region_callbacks

        original = cb.handle_callback
        old_flag = getattr(cb, "_fleet_region_callbacks_installed", False)
        cb._fleet_region_callbacks_installed = False
        patch_fleet_region_callbacks()
        try:
            for data, target in (
                ("fleet:cmd:residence", "diplomacy_bot.fleet_region_hooks.set_fleet_residence"),
                ("fleet:cmd:vote", "diplomacy_bot.fleet_region_hooks.fleet_vote"),
            ):
                query = _Query(datetime.now(timezone.utc) - timedelta(minutes=10))
                with (
                    patch("diplomacy_bot.fleet_ui_markup.fleet_nav_inline_markup", return_value=None),
                    patch(target) as side_effect,
                ):
                    await cb.handle_callback(None, None, data, None, query, 99)
                side_effect.assert_not_called()
                query.message.reply_text.assert_awaited_once()
        finally:
            cb.handle_callback = original
            cb._fleet_region_callbacks_installed = old_flag


if __name__ == "__main__":
    unittest.main()
