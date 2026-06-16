#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_runtime import run_for_account
from diplomacy_bot.store import Account


class AccountRuntimeTests(unittest.TestCase):
    def _acc(self) -> Account:
        return Account(
            id=1,
            name="t",
            token="tok",
            player_id="p1",
            username="T",
            autofarm=False,
            last_farm_at=0,
            last_balance=0,
            proxy_id="tor-01",
            proxy_url="socks5h://127.0.0.1:9050",
            status="active",
        )

    @patch("diplomacy_bot.account_runtime.prepare_egress")
    @patch("diplomacy_bot.account_runtime.set_request_proxy")
    @patch("diplomacy_bot.account_runtime.reset_request_proxy")
    def test_run_for_account(self, reset, set_proxy, prep):
        set_proxy.return_value = "token"
        acc = self._acc()
        out = run_for_account(acc, lambda x: x * 2, 5)
        self.assertEqual(out, 10)
        prep.assert_not_called()
        set_proxy.assert_called_once_with("socks5h://127.0.0.1:9050")
        reset.assert_called_once_with("token")


if __name__ == "__main__":
    unittest.main()
