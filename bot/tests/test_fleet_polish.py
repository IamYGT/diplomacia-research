"""connect_core + inbox state + fleet help testleri."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_command import FleetBatchResult, FleetOpResult
from diplomacy_bot.fleet_help import format_fleet_help_html
from diplomacy_bot.fleet_inbox_import import format_inbox_import_footer
from diplomacy_bot.fleet_ui_markup import fleet_nav_inline_markup
from diplomacy_bot.inbox_processed_state import (
    clear_inbox_processed_for_uid,
    is_inbox_processed,
    load_processed_keys,
    mark_inbox_processed,
)


class ConnectCoreTests(unittest.TestCase):
    def test_connect_core_new_account(self):
        prof = MagicMock(player_id="p99", username="tester", level=3)
        acc = MagicMock(name="u42_w1")
        with (
            patch("diplomacy_bot.auth.resolve_account", return_value=None),
            patch("diplomacy_bot.store.count_accounts_for_user", return_value=1),
            patch("diplomacy_bot.account_pool.suggest_proxy") as sp,
            patch("diplomacy_bot.store.proxy_assignments", return_value={}),
            patch("diplomacy_bot.game_api.get_profile", return_value=prof),
            patch("diplomacy_bot.store.add_account", return_value=acc) as add,
            patch("diplomacy_bot.auto_defaults.apply_auto_defaults_for_new_account"),
            patch("diplomacy_bot.token_meta_store.record_token_saved"),
            patch("diplomacy_bot.account_runtime.account_context"),
        ):
            sp.return_value = MagicMock(id="direct", url="")
            from diplomacy_bot.connect_core import connect_core

            r = connect_core("u42_w1", "eyJtok", telegram_user_id=42)
        self.assertTrue(r.is_new)
        add.assert_called_once()


class InboxProcessedStateTests(unittest.TestCase):
    def test_persist_processed_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inbox_processed.json"
            with patch("diplomacy_bot.inbox_processed_state._STATE_PATH", path):
                mark_inbox_processed(["42:u42_w1"])
                self.assertTrue(is_inbox_processed("42:u42_w1"))
                clear_inbox_processed_for_uid(42)
                self.assertFalse(is_inbox_processed("42:u42_w1"))


class FleetHelpTests(unittest.TestCase):
    def test_fleet_help_has_troubleshooting(self):
        html = format_fleet_help_html()
        self.assertIn("/fleetplan", html)
        self.assertIn("/fleetstart Hürmüz vote", html)
        self.assertIn("/loginkaydet", html)
        self.assertIn("Sorun giderme", html)
        self.assertIn("FLEET_INBOX_AUTO_SETUP", html)

    def test_fleet_help_token_security_hint(self):
        html = format_fleet_help_html()
        self.assertIn("sohbete yapıştırma", html)

    def test_inbox_empty_footer_shows_path(self):
        batch = FleetBatchResult()
        batch.add(FleetOpResult("-", False, "inbox boş"))
        footer = format_inbox_import_footer(515491882, batch)
        self.assertIn("u515491882_01.jwt", footer)

    def test_fleet_result_nav_markup_has_return_paths(self):
        markup = fleet_nav_inline_markup()
        callbacks = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        self.assertEqual(
            callbacks,
            ["fleet:cmd:ops", "fleet:cmd:start", "fleet:menu:more", "fleet:menu:main"],
        )


if __name__ == "__main__":
    unittest.main()
