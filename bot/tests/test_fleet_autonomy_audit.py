#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_autonomy_audit import (
    audit_fleet_autonomy,
    format_fleet_audit_blockers,
    format_fleet_audit_line,
)
from diplomacy_bot.store import Account


def _acc(name: str, *, autofarm: bool = True, status: str = "active") -> Account:
    return Account(
        id=1,
        name=name,
        token="tok",
        player_id="p1",
        username=name,
        autofarm=autofarm,
        last_farm_at=0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status=status,
        telegram_user_id=42,
    )


class FleetAutonomyAuditTests(unittest.TestCase):
    def test_audit_ready_worker(self):
        cfg = MagicMock(
            role="hybrid",
            stat_auto_enabled=True,
            training_enabled=True,
            craft_pills_when_low=True,
            auto_travel_enabled=True,
            auto_token_refresh=True,
            preferred_factory_id="fid",
            work_mode="fixed",
        )
        with patch("diplomacy_bot.fleet_autonomy_audit.get_config", return_value=cfg):
            audit = audit_fleet_autonomy([_acc("main"), _acc("w1")], factory_id="fid", main_account_name="main")

        self.assertEqual((audit.ready, audit.total), (1, 1))
        self.assertIn("1/1", format_fleet_audit_line(audit))
        self.assertEqual(format_fleet_audit_blockers(audit), "")

    def test_audit_reports_blockers(self):
        cfg = MagicMock(
            role="off",
            stat_auto_enabled=False,
            training_enabled=False,
            craft_pills_when_low=False,
            auto_travel_enabled=False,
            auto_token_refresh=True,
            preferred_factory_id="",
            work_mode="own",
        )
        with patch("diplomacy_bot.fleet_autonomy_audit.get_config", return_value=cfg):
            audit = audit_fleet_autonomy([_acc("w1", autofarm=False)], factory_id="fid")

        self.assertEqual((audit.ready, audit.total), (0, 1))
        text = format_fleet_audit_blockers(audit)
        self.assertIn("autofarm kapalı", text)
        self.assertIn("rol off", text)

    def test_audit_reports_missing_token_refresh_source(self):
        cfg = MagicMock(
            role="hybrid",
            stat_auto_enabled=True,
            training_enabled=True,
            craft_pills_when_low=True,
            auto_travel_enabled=True,
            auto_token_refresh=True,
            preferred_factory_id="fid",
            work_mode="fixed",
        )
        with (
            patch("diplomacy_bot.fleet_autonomy_audit.get_config", return_value=cfg),
            patch("diplomacy_bot.fleet_autonomy_audit._has_token_refresh_source", return_value=False),
        ):
            audit = audit_fleet_autonomy([_acc("w1")], factory_id="fid")

        self.assertEqual((audit.ready, audit.total), (0, 1))
        self.assertIn("token refresh kaynağı yok", audit.rows[0].blockers)


if __name__ == "__main__":
    unittest.main()
