"""connect_core account limit tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ConnectCoreTests(unittest.TestCase):
    def test_rejects_21st_account_by_default_limit(self):
        from diplomacy_bot.connect_core import connect_core

        with (
            patch("diplomacy_bot.auth.resolve_account", return_value=None),
            patch("diplomacy_bot.account_main.get_main_account_name", return_value=None),
            patch("diplomacy_bot.store.count_accounts_for_user", return_value=20),
            patch("diplomacy_bot.config.MAX_ACCOUNTS_PER_USER", 20),
        ):
            with self.assertRaisesRegex(ValueError, "En fazla 20 hesap"):
                connect_core("w21", "tok", telegram_user_id=42)

    def test_allows_main_plus_twenty_workers(self):
        from diplomacy_bot.connect_core import connect_core

        profile = SimpleNamespace(player_id="p21", username="W21")
        acc = MagicMock(name="w21")
        with (
            patch("diplomacy_bot.auth.resolve_account", return_value=None),
            patch("diplomacy_bot.account_main.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.store.count_accounts_for_user", return_value=20),
            patch("diplomacy_bot.config.MAX_ACCOUNTS_PER_USER", 20),
            patch("diplomacy_bot.account_pool.suggest_proxy", return_value=SimpleNamespace(id="direct", url="")),
            patch("diplomacy_bot.store.proxy_assignments", return_value={}),
            patch("diplomacy_bot.account_runtime.account_context"),
            patch("diplomacy_bot.game_api.get_profile", return_value=profile),
            patch("diplomacy_bot.store.add_account", return_value=acc),
            patch("diplomacy_bot.auto_defaults.apply_auto_defaults_for_new_account"),
            patch("diplomacy_bot.token_meta_store.record_token_saved"),
        ):
            result = connect_core("w21", "tok", telegram_user_id=42)

        self.assertIs(result.account, acc)
        self.assertTrue(result.is_new)

    def test_rejects_22nd_total_account_when_main_exists(self):
        from diplomacy_bot.connect_core import connect_core

        with (
            patch("diplomacy_bot.auth.resolve_account", return_value=None),
            patch("diplomacy_bot.account_main.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.store.count_accounts_for_user", return_value=21),
            patch("diplomacy_bot.config.MAX_ACCOUNTS_PER_USER", 20),
        ):
            with self.assertRaisesRegex(ValueError, "En fazla 21 hesap"):
                connect_core("w22", "tok", telegram_user_id=42)

    def test_existing_account_refresh_does_not_hit_limit(self):
        from diplomacy_bot.connect_core import connect_core

        existing = MagicMock(name="w1")
        profile = SimpleNamespace(player_id="p1", username="W1")
        acc = MagicMock(name="w1")
        with (
            patch("diplomacy_bot.auth.resolve_account", return_value=existing),
            patch("diplomacy_bot.account_main.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.store.count_accounts_for_user", return_value=20),
            patch("diplomacy_bot.config.MAX_ACCOUNTS_PER_USER", 20),
            patch("diplomacy_bot.account_pool.suggest_proxy", return_value=SimpleNamespace(id="direct", url="")),
            patch("diplomacy_bot.store.proxy_assignments", return_value={}),
            patch("diplomacy_bot.account_runtime.account_context"),
            patch("diplomacy_bot.game_api.get_profile", return_value=profile),
            patch("diplomacy_bot.store.add_account", return_value=acc),
            patch("diplomacy_bot.auto_defaults.apply_auto_defaults_for_new_account") as defaults,
            patch("diplomacy_bot.token_meta_store.record_token_saved"),
        ):
            result = connect_core("w1", "tok2", telegram_user_id=42)

        self.assertIs(result.account, acc)
        self.assertFalse(result.is_new)
        defaults.assert_not_called()


if __name__ == "__main__":
    unittest.main()
