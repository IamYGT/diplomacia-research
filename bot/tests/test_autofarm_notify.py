"""Autofarm bildirim + token recovery testleri."""

from __future__ import annotations

import unittest

from diplomacy_bot.autofarm_notify import (
    format_autofarm_message,
    format_autofarm_success_html,
    reset_recovery_cooldown,
    should_send_recovery_for_account,
    tick_is_token_error,
)
from diplomacy_bot.modules.orchestrator import TickResult
from diplomacy_bot.store import Account


def _acc(name: str = "ygt") -> Account:
    return Account(
        id=1,
        name=name,
        token="x",
        player_id="p1",
        username="YgtUser",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=1000,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=12345,
    )


class AutofarmNotifyTests(unittest.TestCase):
    def test_token_error_returns_no_message(self):
        r = TickResult(account_name="ygt", ok=False, error="Geçersiz token.")
        self.assertTrue(tick_is_token_error(r))
        self.assertIsNone(format_autofarm_message(_acc(), r))

    def test_success_has_earnings(self):
        r = TickResult(
            account_name="ygt",
            username="YgtUser",
            ok=True,
            earned_money=5000,
            balance_after=15000,
            actions=[{"war": True}, {"economy": True}],
        )
        html = format_autofarm_success_html(_acc(), r)
        self.assertIn("Otomatik tur", html)
        self.assertIn("5,000", html)
        self.assertIn("savaş", html)

    def test_recovery_dedupe(self):
        reset_recovery_cooldown("ygt")
        self.assertTrue(should_send_recovery_for_account("ygt"))
        self.assertFalse(should_send_recovery_for_account("ygt"))


if __name__ == "__main__":
    unittest.main()
