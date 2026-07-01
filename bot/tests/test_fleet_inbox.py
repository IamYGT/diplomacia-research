"""Filo inbox import + watch testleri."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from diplomacy_bot.fleet_inbox_import import import_inbox_for_uid
from diplomacy_bot.fleet_inbox_watch import run_auto_inbox_setup_for_uid
from diplomacy_bot.fleet_ui_markup import fleet_more_inline_markup


class FleetInboxImportTests(unittest.TestCase):
    def test_import_inbox_empty(self):
        with patch("diplomacy_bot.token_watch.list_inbox_import_candidates", return_value=[]):
            batch = import_inbox_for_uid(42)
        self.assertEqual(batch.total, 1)
        self.assertFalse(batch.results[0].ok)

    def test_import_inbox_connects(self):
        with (
            patch(
                "diplomacy_bot.token_watch.list_inbox_import_candidates",
                return_value=[("u42_w1", "eyJtok")],
            ),
            patch(
                "diplomacy_bot.fleet_inbox_import.connect_account_sync",
                return_value=MagicMock(name="u42_w1"),
            ) as conn,
        ):
            batch = import_inbox_for_uid(42)
        conn.assert_called_once_with("u42_w1", "eyJtok", telegram_user_id=42)
        self.assertEqual(batch.ok, 1)

    def test_auto_setup_skips_without_fresh(self):
        with patch("diplomacy_bot.token_watch.list_inbox_import_candidates", return_value=[]):
            self.assertIsNone(run_auto_inbox_setup_for_uid(99))

    def test_fleet_more_menu_has_back_button(self):
        rows = fleet_more_inline_markup().inline_keyboard
        back = rows[-1][0]
        self.assertEqual(back.callback_data, "fleet:menu:main")
        self.assertIn("Filo", back.text)


if __name__ == "__main__":
    unittest.main()
