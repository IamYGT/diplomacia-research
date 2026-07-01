"""account_balance testleri."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_balance import (
    DisplayBalance,
    persist_last_balance,
    refresh_display_balances,
    resolve_display_balance,
)
from diplomacy_bot.store import Account, add_account, get_account, init_db


def _acc(name: str, bal: int = 0) -> Account:
    return Account(
        id=1,
        name=name,
        token="tok",
        player_id="p1",
        username="U",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=bal,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )


class AccountBalanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_stale_shows_tilde(self):
        info = resolve_display_balance(_acc("a", 1250))
        self.assertEqual(info.source, "stale")
        self.assertEqual(info.format(), "~1,250₺")

    def test_token_error_marker(self):
        info = DisplayBalance(1250, "stale", token_error=True)
        self.assertEqual(info.format(), "~1,250₺ 🔑")

    def test_refresh_live_updates_db(self):
        with patch("diplomacy_bot.config.DB_PATH", self.db), patch(
            "diplomacy_bot.store.DB_PATH", self.db
        ):
            init_db()
            add_account("u1_bal", "tok", "p1", "U1", telegram_user_id=1)
            prof = MagicMock(balance=99999)
            with patch("diplomacy_bot.game_api.get_profile", return_value=prof):
                out = refresh_display_balances([get_account("u1_bal")])
            self.assertEqual(out["u1_bal"].amount, 99999)
            self.assertEqual(out["u1_bal"].source, "live")
            self.assertEqual(get_account("u1_bal").last_balance, 99999)

    def test_refresh_token_error_keeps_stale(self):
        with patch("diplomacy_bot.config.DB_PATH", self.db), patch(
            "diplomacy_bot.store.DB_PATH", self.db
        ):
            init_db()
            add_account("u1_stale", "tok", "p1", "U1", telegram_user_id=1)
            persist_last_balance("u1_stale", 1250)
            with patch(
                "diplomacy_bot.game_api.get_profile",
                side_effect=RuntimeError("Oturum süresi doldu"),
            ):
                out = refresh_display_balances([get_account("u1_stale")])
            self.assertTrue(out["u1_stale"].token_error)
            self.assertEqual(out["u1_stale"].format(), "~1,250₺ 🔑")

    def test_persist_last_balance(self):
        with patch("diplomacy_bot.config.DB_PATH", self.db), patch(
            "diplomacy_bot.store.DB_PATH", self.db
        ):
            init_db()
            add_account("u1_persist", "t", "p", "X", telegram_user_id=1)
            persist_last_balance("u1_persist", 42000)
            self.assertEqual(get_account("u1_persist").last_balance, 42000)


if __name__ == "__main__":
    unittest.main()
