"""Filo inbox import + watch testleri."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_inbox_import import import_inbox_for_uid
from diplomacy_bot.fleet_inbox_watch import run_auto_inbox_setup_for_uid
from diplomacy_bot.fleet_command import FleetBatchResult, FleetOpResult
from diplomacy_bot.fleet_ui_markup import fleet_more_inline_markup, patch_fleet_ui_buttons


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

    def test_auto_setup_runs_autopilot_for_fresh_candidate(self):
        result = MagicMock()
        result.inbox = FleetBatchResult()
        result.inbox.add(FleetOpResult("u42_w1", True, "bağlandı"))
        with (
            patch("diplomacy_bot.token_watch.list_inbox_import_candidates", return_value=[("u42_w1", "tok")]),
            patch("diplomacy_bot.fleet_inbox_watch.is_inbox_processed", return_value=False),
            patch("diplomacy_bot.fleet_inbox_watch.mark_inbox_processed") as mark,
            patch(
                "diplomacy_bot.fleet_mission_service.start_fleet_autopilot_for_uid",
                return_value=result,
            ) as start,
        ):
            got = run_auto_inbox_setup_for_uid(42)

        self.assertEqual(got, result)
        start.assert_called_once_with(42)
        mark.assert_called_once_with({"42:u42_w1"})

    def test_auto_setup_does_not_mark_failed_import_processed(self):
        result = MagicMock()
        result.inbox = FleetBatchResult()
        result.inbox.add(FleetOpResult("u42_w1", False, "token expired"))
        with (
            patch("diplomacy_bot.token_watch.list_inbox_import_candidates", return_value=[("u42_w1", "tok")]),
            patch("diplomacy_bot.fleet_inbox_watch.is_inbox_processed", return_value=False),
            patch("diplomacy_bot.fleet_inbox_watch.mark_inbox_processed") as mark,
            patch(
                "diplomacy_bot.fleet_mission_service.start_fleet_autopilot_for_uid",
                return_value=result,
            ),
        ):
            got = run_auto_inbox_setup_for_uid(42)

        self.assertEqual(got, result)
        mark.assert_not_called()

    def test_fleet_more_menu_has_back_button(self):
        rows = fleet_more_inline_markup().inline_keyboard
        back = rows[-1][0]
        self.assertEqual(back.callback_data, "fleet:menu:main")
        self.assertIn("Filo", back.text)

    def test_fleet_more_menu_has_no_duplicate_hybrid_bootstrap(self):
        rows = fleet_more_inline_markup().inline_keyboard
        callbacks = [button.callback_data for row in rows for button in row]
        labels = [button.text for row in rows for button in row]

        self.assertIn("fleet:cmd:bootstrap", callbacks)
        self.assertNotIn("fleet:af:on:hybrid", callbacks)
        self.assertIn("🚀 Hazırla", labels)

    def test_fleet_main_menu_has_start_button(self):
        from diplomacy_bot import telegram_ui as ui

        patch_fleet_ui_buttons()
        rows = ui.fleet_inline_markup("w1", []).inline_keyboard
        callbacks = [button.callback_data for row in rows for button in row]

        self.assertIn("fleet:cmd:start", callbacks)
        self.assertIn("fleet:cmd:ops", callbacks)
        self.assertIn("fleet:menu:more", callbacks)

    def test_fleet_main_menu_hides_technical_tick_buttons(self):
        from diplomacy_bot import telegram_ui as ui

        patch_fleet_ui_buttons()
        rows = ui.fleet_inline_markup("w1", []).inline_keyboard
        callbacks = [button.callback_data for row in rows for button in row]

        self.assertNotIn("fleet:tick:farm", callbacks)
        self.assertNotIn("fleet:af:on:farm", callbacks)


if __name__ == "__main__":
    unittest.main()
