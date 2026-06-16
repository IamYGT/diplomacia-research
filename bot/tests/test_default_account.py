#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.store import Account
from diplomacy_bot import telegram_helpers


def _ygt() -> Account:
    return Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="YGT",
        autofarm=True,
        last_farm_at=0,
        last_balance=0,
        proxy_id="tor-01",
        proxy_url="",
        status="active",
        telegram_user_id=42,
    )


class DefaultAccountTests(unittest.TestCase):
    def test_stale_name_falls_back_to_user_account(self):
        ctx = MagicMock()
        ctx.user_data = {"default_account": "ercan2"}
        update = MagicMock()
        update.effective_user.id = 42

        with (
            patch("diplomacy_bot.telegram_helpers.resolve_account", return_value=None),
            patch("diplomacy_bot.telegram_helpers._user_accounts", return_value=[_ygt()]),
            patch("diplomacy_bot.telegram_helpers.get_session", return_value=None),
            patch("diplomacy_bot.telegram_helpers.upsert_session"),
        ):
            name = telegram_helpers._default_account(ctx, 42)

        self.assertEqual(name, "ygt")
        self.assertEqual(ctx.user_data["default_account"], "ygt")

    def test_valid_stored_default_kept(self):
        ctx = MagicMock()
        ctx.user_data = {"default_account": "ygt"}

        with (
            patch("diplomacy_bot.telegram_helpers.resolve_account", return_value=_ygt()),
            patch("diplomacy_bot.telegram_helpers.get_session", return_value=None),
        ):
            name = telegram_helpers._default_account(ctx, 42)

        self.assertEqual(name, "ygt")

    def test_no_accounts_returns_none(self):
        ctx = MagicMock()
        ctx.user_data = {}

        with (
            patch("diplomacy_bot.telegram_helpers._user_accounts", return_value=[]),
            patch("diplomacy_bot.telegram_helpers.get_session", return_value=None),
        ):
            name = telegram_helpers._default_account(ctx, 42)

        self.assertIsNone(name)


if __name__ == "__main__":
    unittest.main()
