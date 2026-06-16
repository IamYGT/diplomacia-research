#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import dynamic_context, store
from diplomacy_bot.db_migrate import CURRENT_SCHEMA_VERSION


class DbPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.data = Path(self.tmp.name) / "data"

    def tearDown(self):
        dynamic_context._SNAPSHOT_CACHE.clear()
        self.tmp.cleanup()

    def _init(self):
        with (
            patch.object(store, "DB_PATH", self.db),
            patch.object(store, "DATA_DIR", self.data),
        ):
            store.init_db()

    def test_schema_migrations_applied(self):
        self._init()
        with patch.object(store, "DB_PATH", self.db):
            with store._conn() as c:
                row = c.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
                self.assertEqual(int(row["v"]), CURRENT_SCHEMA_VERSION)

    def test_add_account_stores_plain_jwt(self):
        self._init()
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sig"
        with patch.object(store, "DB_PATH", self.db):
            acc = store.add_account("u1", jwt, "p1", "U1", telegram_user_id=1)
            self.assertEqual(acc.token, jwt)
            with store._conn() as c:
                row = c.execute("SELECT token, token_enc FROM accounts WHERE name='u1'").fetchone()
                self.assertEqual(row["token"], jwt)
                self.assertIn(row["token_enc"], ("", None))

    def test_game_snapshot_persist(self):
        self._init()
        with patch.object(store, "DB_PATH", self.db):
            store.save_game_snapshot("u1", {"level": 5, "username": "X"}, ttl_sec=60)
            snap = store.get_game_snapshot("u1", max_age_sec=120)
            self.assertEqual(snap["level"], 5)
            store.delete_game_snapshot("u1")
            self.assertIsNone(store.get_game_snapshot("u1"))

    def test_bot_session_roundtrip(self):
        self._init()
        with patch.object(store, "DB_PATH", self.db):
            store.upsert_session(42, active_account="u1", pending_connect=True)
            sess = store.get_session(42)
            self.assertEqual(sess["active_account"], "u1")
            self.assertEqual(int(sess["pending_connect"]), 1)

    def test_action_log(self):
        self._init()
        with patch.object(store, "DB_PATH", self.db):
            store.log_action("farm", account_name="u1", telegram_user_id=9, result="ok")
            rows = store.recent_actions("u1", limit=5)
            self.assertEqual(rows[0]["action"], "farm")

    def test_peek_snapshot_from_db_after_memory_clear(self):
        self._init()
        with patch.object(store, "DB_PATH", self.db):
            store.save_game_snapshot("u1", {"username": "U", "level": 3, "_live": True}, ttl_sec=90)
            dynamic_context._SNAPSHOT_CACHE.clear()
            peek = dynamic_context.peek_snapshot_cache("u1", allow_stale=True)
        self.assertIsNotNone(peek)
        self.assertEqual(peek["level"], 3)


if __name__ == "__main__":
    unittest.main()
