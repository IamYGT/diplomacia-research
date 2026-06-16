#!/usr/bin/env python3
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import dynamic_context
from diplomacy_bot.store import Account


def _acc() -> Account:
    return Account(
        id=1,
        name="u1",
        token="t",
        player_id="p",
        username="U",
        autofarm=False,
        last_farm_at=0,
        last_balance=0,
        proxy_id="tor-01",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )


class SnapshotCacheTests(unittest.TestCase):
    def setUp(self):
        dynamic_context._SNAPSHOT_CACHE.clear()

    def test_peek_stale_extends_visibility(self):
        dynamic_context._SNAPSHOT_CACHE["u1"] = (time.time() - 30, {"username": "U", "level": 1, "_live": True})
        self.assertIsNone(dynamic_context.peek_snapshot_cache("u1"))
        stale = dynamic_context.peek_snapshot_cache("u1", allow_stale=True)
        self.assertIsNotNone(stale)
        self.assertEqual(stale["username"], "U")

    def test_is_snapshot_fresh(self):
        dynamic_context._SNAPSHOT_CACHE["u1"] = (time.time() - 5, {"ok": True})
        self.assertTrue(dynamic_context.is_snapshot_fresh("u1"))
        dynamic_context._SNAPSHOT_CACHE["u1"] = (time.time() - 100, {"ok": True})
        self.assertFalse(dynamic_context.is_snapshot_fresh("u1"))


if __name__ == "__main__":
    unittest.main()
