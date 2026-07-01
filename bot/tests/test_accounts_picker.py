"""accounts_picker + scoped_list_accounts testleri."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import auth, store
from diplomacy_bot.accounts_picker import (
    accounts_inline_markup,
    format_accounts_html,
    sort_accounts_for_display,
)
from diplomacy_bot.store import Account


def _acc(name: str, uid: int, username: str = "u", main: bool = False) -> Account:
    return Account(
        id=1,
        name=name,
        token="tok",
        player_id="p1",
        username=username,
        autofarm=True,
        last_farm_at=0.0,
        last_balance=1000,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=uid,
    )


class AccountsPickerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_admin_scoped_only_own_accounts(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)
            with patch.object(auth, "TELEGRAM_ADMIN_IDS", {100}):
                names = [a.name for a in auth.scoped_list_accounts(100)]
            self.assertEqual(names, ["u100_a"])
            self.assertNotIn("u200_b", names)

    def test_sort_main_first(self):
        accs = [
            _acc("u1_b", 1, "B"),
            _acc("u1_a", 1, "A"),
        ]
        with patch("diplomacy_bot.accounts_picker.get_main_account_name", return_value="u1_a"):
            ordered = sort_accounts_for_display(accs, telegram_user_id=1, active_name="u1_b")
        self.assertEqual([a.name for a in ordered], ["u1_a", "u1_b"])

    def test_format_shows_count_not_foreign_test_account(self):
        accs = [_acc("ygt", 515491882, "Y.G.T"), _acc("u515491882_ygt1", 515491882, "Y.G.T1")]
        html = format_accounts_html("ygt", accs, telegram_user_id=515491882)
        self.assertIn("2/", html)
        self.assertNotIn("auto_def_test", html)

    def test_markup_two_columns(self):
        accs = [_acc("ygt", 1), _acc("alt", 1)]
        mk = accounts_inline_markup("ygt", accs, telegram_user_id=1)
        first_row = mk.inline_keyboard[0]
        self.assertEqual(len(first_row), 2)


if __name__ == "__main__":
    unittest.main()
