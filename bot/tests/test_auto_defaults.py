"""Yeni hesap otomatik özellik varsayılanları."""

from __future__ import annotations

import unittest


class AutoDefaultsTests(unittest.TestCase):
    def test_apply_enables_autofarm_and_config_flags(self):
        from diplomacy_bot.account_config import get_config
        from diplomacy_bot.auto_defaults import AUTO_FEATURE_FIELDS, apply_auto_defaults_for_new_account
        from diplomacy_bot.store import add_account, get_account, set_autofarm

        name = "auto_def_test"
        add_account(name, "eyJfake.token.here", "pid_auto", "user", telegram_user_id=99901)
        set_autofarm(name, False)
        apply_auto_defaults_for_new_account(name)
        acc = get_account(name)
        self.assertTrue(acc.autofarm)
        cfg = get_config(name)
        for field in AUTO_FEATURE_FIELDS:
            self.assertTrue(getattr(cfg, field), f"{field} should be True")

    def test_fresh_config_dataclass_defaults(self):
        from diplomacy_bot.account_config import AccountConfig

        cfg = AccountConfig(account_name="fresh")
        self.assertTrue(cfg.auto_like_articles)
        self.assertTrue(cfg.auto_travel_enabled)
        self.assertTrue(cfg.auto_token_refresh)
        self.assertTrue(cfg.auto_daily_claim)
        self.assertTrue(cfg.auto_quest_claim)

    def test_connected_html_mentions_auto_for_new(self):
        from types import SimpleNamespace

        from diplomacy_bot.connect_intel import format_account_connected_html

        prof = SimpleNamespace(username="tester", balance=100, level=3)
        html = format_account_connected_html("u1_test", prof, telegram_user_id=1, is_new_account=True)
        self.assertIn("Otomatik özellikler açık", html)


if __name__ == "__main__":
    unittest.main()
