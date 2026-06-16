#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig, apply_role_defaults, normalize_role, role_label
from diplomacy_bot.fleet_manager import accounts_for_role, count_by_role
from diplomacy_bot.store import Account


def _acc(name: str = "a1") -> Account:
    return Account(
        id=1,
        name=name,
        token="t",
        player_id="p",
        username="U",
        autofarm=True,
        last_farm_at=0,
        last_balance=1000,
        proxy_id="tor-01",
        proxy_url="",
        status="active",
    )


class RoleConfigTests(unittest.TestCase):
    def test_normalize_legacy_farmer(self):
        self.assertEqual(normalize_role("farmer"), "farm")

    def test_war_role_enables_war(self):
        cfg = apply_role_defaults(AccountConfig(account_name="x", role="war"))
        self.assertTrue(cfg.war_enabled)
        self.assertEqual(normalize_role(cfg.role), "war")

    def test_farm_role_disables_war(self):
        cfg = apply_role_defaults(AccountConfig(account_name="x", role="farm"))
        self.assertFalse(cfg.war_enabled)

    def test_role_label_tr(self):
        self.assertIn("Farm", role_label("farm"))


class FleetFilterTests(unittest.TestCase):
    @patch("diplomacy_bot.fleet_manager.list_accounts")
    @patch("diplomacy_bot.fleet_manager.get_config")
    def test_accounts_for_war_role(self, mock_cfg, mock_list):
        mock_list.return_value = [_acc("w1"), _acc("f1")]
        mock_cfg.side_effect = lambda n: AccountConfig(
            account_name=n,
            role="war" if n == "w1" else "farm",
        )

        war_accs = accounts_for_role("war")
        self.assertEqual([a.name for a in war_accs], ["w1"])


if __name__ == "__main__":
    unittest.main()
