#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_autonomy_audit import FleetAudit, FleetAuditRow
from diplomacy_bot.fleet_blocker_summary import format_fleet_blocker_summary
from diplomacy_bot.store import Account


def _acc(name: str, *, state: str = "idle") -> Account:
    return Account(
        id=1,
        name=name,
        token="tok",
        player_id=name,
        username=name,
        autofarm=True,
        last_farm_at=0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=42,
        runtime_state=state,
    )


class FleetBlockerSummaryTests(unittest.TestCase):
    def test_summary_combines_audit_runtime_and_training_skips(self):
        audit = FleetAudit(
            total=3,
            ready=2,
            rows=[
                FleetAuditRow("w1", True),
                FleetAuditRow("w2", False, ["ana fabrikaya sabit değil"]),
                FleetAuditRow("w3", True),
            ],
        )
        with patch(
            "diplomacy_bot.action_log_query.count_action_results_since",
            return_value={"no_training_war": 2, "training_exception": 1, "ignored": 9},
        ), patch(
            "diplomacy_bot.action_log_query.count_actions_since",
            return_value=1,
        ):
            text = format_fleet_blocker_summary([_acc("w1", state="cooldown"), _acc("w2"), _acc("w3")], audit)

        self.assertIn("1 hazır değil", text)
        self.assertIn("1 cooldown", text)
        self.assertIn("2 training savaş yok", text)
        self.assertIn("1 training hata", text)
        self.assertIn("1 mission hata", text)

    def test_summary_reports_no_visible_blocker_when_ready(self):
        audit = FleetAudit(total=1, ready=1, rows=[FleetAuditRow("w1", True)])
        with (
            patch("diplomacy_bot.action_log_query.count_action_results_since", return_value={}),
            patch("diplomacy_bot.action_log_query.count_actions_since", return_value=0),
        ):
            text = format_fleet_blocker_summary([_acc("w1")], audit)

        self.assertIn("görünür engel yok", text)


if __name__ == "__main__":
    unittest.main()
