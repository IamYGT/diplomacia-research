"""Tab callback entegrasyon testleri."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from diplomacy_bot.tab_nav import tab_nav_row


class TabNavCallbackTests(unittest.TestCase):
    def test_war_travel_callbacks(self):
        row = tab_nav_row(active="home")
        data = {b.callback_data for b in row}
        self.assertEqual(data, {"dash:home", "menu:war", "menu:travel"})


class TabHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_menu_war_delegates(self):
        from diplomacy_bot.telegram_tabs import handle_tab_menu_callback

        query = MagicMock()
        query.message = MagicMock()
        with patch(
            "diplomacy_bot.telegram_tabs.open_war_tab",
            new_callable=AsyncMock,
        ) as war_mock:
            handled = await handle_tab_menu_callback(
                "menu:war", query, 1, "ygt", MagicMock()
            )
            self.assertTrue(handled)
            war_mock.assert_awaited_once()

    async def test_keyboard_toggle(self):
        from diplomacy_bot.telegram_tabs import handle_tab_menu_callback

        query = MagicMock()
        query.message = MagicMock()
        query.message.reply_text = AsyncMock()
        query.answer = AsyncMock()
        with (
            patch("diplomacy_bot.telegram_tabs.toggle_reply_keyboard", return_value=False),
            patch("diplomacy_bot.telegram_tabs.reply_keyboard_for_user", return_value=None),
            patch(
                "diplomacy_bot.telegram_helpers._send_settings",
                new_callable=AsyncMock,
            ),
        ):
            handled = await handle_tab_menu_callback(
                "cfg:keyboard:toggle", query, 5, "ygt", MagicMock()
            )
            self.assertTrue(handled)


if __name__ == "__main__":
    unittest.main()
