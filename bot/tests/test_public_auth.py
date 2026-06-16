#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import auth, store


class PublicAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_account_name(self):
        self.assertEqual(auth.default_account_name(12345), "u12345")
        self.assertEqual(auth.default_account_name(12345, "alt"), "u12345_alt")

    def test_owner_scoped_access(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            a1 = store.add_account("u1", "tok1", "p1", "U1", telegram_user_id=100)
            a2 = store.add_account("u2", "tok2", "p2", "U2", telegram_user_id=200)
            self.assertEqual(len(store.list_accounts_for_user(100)), 1)
            self.assertEqual(store.list_accounts_for_user(100)[0].name, "u1")
            self.assertIsNone(auth.resolve_account("u2", 100))
            with patch.object(auth, "TELEGRAM_ADMIN_IDS", {999}):
                self.assertIsNotNone(auth.resolve_account("u2", 999))

    def test_player_id_conflict(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100", "t1", "player-x", "A", telegram_user_id=100)
            with self.assertRaises(ValueError):
                store.add_account("u200", "t2", "player-x", "B", telegram_user_id=200)


if __name__ == "__main__":
    unittest.main()
