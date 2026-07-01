"""M3 store facade + sqlite adapter testleri."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import store
from diplomacy_bot.adapters.sqlite import accounts_repo, snapshots


class StoreFacadeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_facade_roundtrip(self):
        with patch("diplomacy_bot.config.DB_PATH", self.db):
            store.init_db()
            store.add_account("u1", "eyJhbGciOiJIUzI1NiIs.test", "p1", "U1", telegram_user_id=1)
            acc = store.get_account("u1")
            self.assertIsNotNone(acc)
            self.assertEqual(acc.username, "U1")
            store.save_game_snapshot("u1", {"balance": 100, "_live": True}, ttl_sec=90)
            snap = store.get_game_snapshot("u1")
            self.assertEqual(snap.get("balance"), 100)

    def test_accounts_repo_direct(self):
        with patch("diplomacy_bot.config.DB_PATH", self.db):
            accounts_repo.init_accounts_table()
            accounts_repo.add_account("a", "tok", telegram_user_id=2)
            self.assertEqual(len(accounts_repo.list_accounts_for_user(2)), 1)

    def test_store_conn_alias(self):
        self.assertTrue(callable(store._conn))


if __name__ == "__main__":
    unittest.main()
