"""token_db — DB tek kaynak testleri."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import store
from diplomacy_bot.token_db import get_stored_token, persist_account_token
from diplomacy_bot.token_watch import TOKEN_INBOX, consume_inbox_for_account


class TokenDbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.inbox = Path(self.tmp.name) / "inbox"
        self.inbox.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_persist_writes_db_only(self):
        with patch("diplomacy_bot.config.DB_PATH", self.db), patch(
            "diplomacy_bot.store.DB_PATH", self.db
        ), patch("diplomacy_bot.token_watch.TOKEN_INBOX", self.inbox):
            store.init_db()
            prof = MagicMock(player_id="pid1", username="U1", balance=100)
            with patch("diplomacy_bot.game_api.get_profile", return_value=prof), patch(
                "diplomacy_bot.account_pool.suggest_proxy"
            ) as sp:
                sp.return_value = MagicMock(id="direct", url="")
                persist_account_token("u1_a", "eyJhbGciOiJIUzI1NiIs.test", telegram_user_id=100)
            self.assertTrue(get_stored_token("u1_a").startswith("eyJ"))

    def test_consume_inbox_after_import(self):
        with patch("diplomacy_bot.token_watch.TOKEN_INBOX", self.inbox):
            f = self.inbox / "ygt.jwt"
            f.write_text("eyJx", encoding="utf-8")
            self.assertTrue(consume_inbox_for_account("ygt"))
            self.assertFalse(f.exists())


if __name__ == "__main__":
    unittest.main()
