"""Dashboard pin ve flood patch testleri."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from diplomacy_bot.dashboard_session import (
    clear_dashboard_pin,
    get_dashboard_pin,
    set_dashboard_pin,
)
from diplomacy_bot.easy_mode import format_onboarding_guide_html


class DashboardSessionTests(unittest.TestCase):
    def setUp(self):
        from diplomacy_bot import store

        self.tmp = store.DATA_DIR / "test_dash_pin"
        self._orig = store.DATA_DIR
        store.DATA_DIR = self.tmp
        store.init_db()

    def tearDown(self):
        from diplomacy_bot import store

        store.DATA_DIR = self._orig

    def test_pin_roundtrip(self):
        set_dashboard_pin(42, 100, 200)
        self.assertEqual(get_dashboard_pin(42), (100, 200))
        clear_dashboard_pin(42)
        self.assertIsNone(get_dashboard_pin(42))


class OnboardingKeyboardNoteTests(unittest.TestCase):
    def test_hidden_keyboard_note(self):
        text = format_onboarding_guide_html(keyboard_hidden=True)
        self.assertIn("Savaş", text)
        self.assertIn("Seyahat", text)

    def test_visible_keyboard_note(self):
        text = format_onboarding_guide_html(keyboard_hidden=False)
        self.assertIn("Ana Sayfa", text)


class DashboardFloodPatchTests(unittest.IsolatedAsyncioTestCase):
    def _account(self):
        from diplomacy_bot.store import Account

        return Account(
            id=1,
            name="ygt",
            token="t",
            player_id="p",
            username="Y",
            autofarm=False,
            last_farm_at=0,
            last_balance=0,
            proxy_id="",
            proxy_url="",
            status="active",
        )

    def _snap(self):
        return {
            "username": "Y",
            "level": 1,
            "class": "x",
            "province": "p",
            "country": "c",
            "balance": 0,
            "diamonds": 0,
            "health": 100,
            "pills": 0,
            "work_ready": True,
            "passive_available": 0,
            "autofarm": False,
        }

    async def test_keyboard_dashboard_new_message_without_pin(self):
        from diplomacy_bot import telegram_app as ta
        from diplomacy_bot.dashboard_flood import install_dashboard_flood_patch

        install_dashboard_flood_patch()
        acc = self._account()
        update = MagicMock()
        update.callback_query = None
        msg = MagicMock()
        msg.chat_id = 1
        update.effective_message = msg
        update.get_bot.return_value = AsyncMock()
        sent = MagicMock()
        sent.chat_id = 1
        sent.message_id = 99
        msg.reply_text = AsyncMock(return_value=sent)
        context = MagicMock()

        with (
            patch("diplomacy_bot.telegram_app._uid", return_value=1),
            patch("diplomacy_bot.telegram_app._user_accounts", return_value=[]),
            patch("diplomacy_bot.dynamic_context.peek_snapshot_cache", return_value=self._snap()),
            patch("diplomacy_bot.dashboard_flood.get_dashboard_pin", return_value=None),
            patch(
                "diplomacy_bot.dashboard_flood.delete_pinned_dashboard",
                new_callable=AsyncMock,
            ) as del_mock,
        ):
            await ta._open_dashboard_tracked(update, context, acc, edit=False)
            del_mock.assert_not_awaited()
            msg.reply_text.assert_awaited_once()
            self.assertEqual(get_dashboard_pin(1), (1, 99))

    async def test_keyboard_dashboard_edits_pinned_message(self):
        from diplomacy_bot import telegram_app as ta
        from diplomacy_bot.dashboard_flood import install_dashboard_flood_patch

        install_dashboard_flood_patch()
        acc = self._account()
        update = MagicMock()
        update.callback_query = None
        msg = MagicMock()
        msg.chat_id = 1
        update.effective_message = msg
        update.get_bot.return_value = AsyncMock()
        msg.reply_text = AsyncMock()
        context = MagicMock()

        with (
            patch("diplomacy_bot.telegram_app._uid", return_value=7),
            patch("diplomacy_bot.telegram_app._user_accounts", return_value=[]),
            patch("diplomacy_bot.dynamic_context.peek_snapshot_cache", return_value=self._snap()),
            patch("diplomacy_bot.dashboard_flood.get_dashboard_pin", return_value=(1, 55)),
            patch(
                "diplomacy_bot.dashboard_flood.delete_pinned_dashboard",
                new_callable=AsyncMock,
            ) as del_mock,
            patch(
                "diplomacy_bot.dashboard_flood.edit_safe",
                new_callable=AsyncMock,
                return_value=True,
            ) as edit_mock,
        ):
            await ta._open_dashboard_tracked(update, context, acc, edit=False)
            del_mock.assert_not_awaited()
            msg.reply_text.assert_not_awaited()
            edit_mock.assert_awaited()
            self.assertEqual(edit_mock.await_args.args[1], 1)
            self.assertEqual(edit_mock.await_args.args[2], 55)

    async def test_keyboard_dashboard_fallback_when_edit_fails(self):
        from diplomacy_bot import telegram_app as ta
        from diplomacy_bot.dashboard_flood import install_dashboard_flood_patch

        install_dashboard_flood_patch()
        acc = self._account()
        update = MagicMock()
        update.callback_query = None
        msg = MagicMock()
        msg.chat_id = 1
        update.effective_message = msg
        update.get_bot.return_value = AsyncMock()
        sent = MagicMock()
        sent.chat_id = 1
        sent.message_id = 88
        msg.reply_text = AsyncMock(return_value=sent)
        context = MagicMock()

        with (
            patch("diplomacy_bot.telegram_app._uid", return_value=3),
            patch("diplomacy_bot.telegram_app._user_accounts", return_value=[]),
            patch("diplomacy_bot.dynamic_context.peek_snapshot_cache", return_value=self._snap()),
            patch("diplomacy_bot.dashboard_flood.get_dashboard_pin", return_value=(1, 55)),
            patch(
                "diplomacy_bot.dashboard_flood.edit_safe",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("diplomacy_bot.dashboard_flood.clear_dashboard_pin") as clear_mock,
        ):
            await ta._open_dashboard_tracked(update, context, acc, edit=False)
            clear_mock.assert_called_once_with(3)
            msg.reply_text.assert_awaited_once()
            self.assertEqual(get_dashboard_pin(3), (1, 88))

    async def test_placeholder_spawns_dashboard_fetch(self):
        from diplomacy_bot import telegram_app as ta
        from diplomacy_bot.dashboard_flood import install_dashboard_flood_patch

        install_dashboard_flood_patch()
        acc = self._account()
        update = MagicMock()
        update.callback_query = None
        msg = MagicMock()
        msg.chat_id = 1
        update.effective_message = msg
        update.get_bot.return_value = AsyncMock()
        sent = MagicMock()
        sent.chat_id = 1
        sent.message_id = 77
        msg.reply_text = AsyncMock(return_value=sent)
        context = MagicMock()
        context.application.create_task = MagicMock(side_effect=lambda c, name=None: c)

        with (
            patch("diplomacy_bot.telegram_app._uid", return_value=5),
            patch("diplomacy_bot.telegram_app._user_accounts", return_value=[]),
            patch("diplomacy_bot.dashboard_flood.peek_snapshot_cache", return_value=None),
            patch("diplomacy_bot.dashboard_flood.is_snapshot_fresh", return_value=False),
            patch("diplomacy_bot.dashboard_flood.get_dashboard_pin", return_value=None),
            patch(
                "diplomacy_bot.telegram_app._publish_dashboard_message",
                new_callable=AsyncMock,
            ) as publish_mock,
        ):
            await ta._open_dashboard_tracked(update, context, acc, edit=False)
            publish_mock.assert_called_once()
            self.assertTrue(publish_mock.call_args.kwargs.get("force_refresh"))

    async def test_keyboard_dashboard_migrates_other_chat_pin(self):
        from diplomacy_bot import telegram_app as ta
        from diplomacy_bot.dashboard_flood import install_dashboard_flood_patch

        install_dashboard_flood_patch()
        acc = self._account()
        update = MagicMock()
        update.callback_query = None
        msg = MagicMock()
        msg.chat_id = 99
        update.effective_message = msg
        update.get_bot.return_value = AsyncMock()
        sent = MagicMock()
        sent.chat_id = 99
        sent.message_id = 12
        msg.reply_text = AsyncMock(return_value=sent)
        context = MagicMock()

        with (
            patch("diplomacy_bot.telegram_app._uid", return_value=4),
            patch("diplomacy_bot.telegram_app._user_accounts", return_value=[]),
            patch("diplomacy_bot.dynamic_context.peek_snapshot_cache", return_value=self._snap()),
            patch("diplomacy_bot.dashboard_flood.get_dashboard_pin", return_value=(1, 55)),
            patch(
                "diplomacy_bot.dashboard_flood.delete_pinned_dashboard",
                new_callable=AsyncMock,
            ) as del_mock,
        ):
            await ta._open_dashboard_tracked(update, context, acc, edit=False)
            del_mock.assert_awaited_once()
            msg.reply_text.assert_awaited_once()
            self.assertEqual(get_dashboard_pin(4), (99, 12))


class GlobalKeyboardPatchTests(unittest.TestCase):
    def test_global_keyboard_respects_uid_pref(self):
        from diplomacy_bot import telegram_ui as ui
        from diplomacy_bot.keyboard_reply import install_global_reply_keyboard, user_reply_keyboard
        from diplomacy_bot.bootstrap.hooks.reply_keyboard_entries import install_reply_keyboard_entries

        install_reply_keyboard_entries()
        install_global_reply_keyboard()

        async def _run():
            async with user_reply_keyboard(12345):
                from diplomacy_bot.keyboard_prefs import set_reply_keyboard_enabled

                set_reply_keyboard_enabled(12345, False)
                kb = ui.main_reply_keyboard()
                return type(kb).__name__

        import asyncio

        name = asyncio.run(_run())
        self.assertIn("Remove", name)


class TabHookChainTests(unittest.TestCase):
    def test_tab_hook_outermost(self):
        from diplomacy_bot import callbacks as cb
        from diplomacy_bot import telegram_app as ta
        from diplomacy_bot.bootstrap import install_bootstrap

        install_bootstrap()
        self.assertIs(cb.handle_callback, ta._handle_callback)
        # Token recovery en dış callback sarmalayıcı
        self.assertTrue(cb.handle_callback.__name__ == "handle_callback_patched")


if __name__ == "__main__":
    unittest.main()
