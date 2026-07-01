"""action_log_query + fleet_metrics testleri."""

from __future__ import annotations

import tempfile
import time
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_metrics import count_fleet_training_waiting, format_fleet_metrics_line


class FleetMetricsTests(unittest.TestCase):
    def test_format_metrics_empty_when_no_activity(self):
        with (
            patch("diplomacy_bot.fleet_metrics.scoped_list_accounts", return_value=[]),
            patch("diplomacy_bot.fleet_metrics.count_fleet_farms_24h", return_value=0),
            patch("diplomacy_bot.fleet_metrics.count_fleet_training_attacks_24h", return_value=0),
            patch("diplomacy_bot.fleet_metrics.count_fleet_training_skips_24h", return_value=0),
            patch("diplomacy_bot.fleet_metrics.count_fleet_training_waiting", return_value=0),
        ):
            self.assertEqual(format_fleet_metrics_line(1), "")

    def test_format_metrics_line(self):
        with (
            patch("diplomacy_bot.fleet_metrics.count_fleet_farms_24h", return_value=12),
            patch("diplomacy_bot.fleet_metrics.count_fleet_training_attacks_24h", return_value=3),
            patch("diplomacy_bot.fleet_metrics.count_fleet_training_skips_24h", return_value=2),
            patch("diplomacy_bot.fleet_metrics.count_fleet_training_waiting", return_value=4),
        ):
            line = format_fleet_metrics_line(42)
        self.assertIn("12", line)
        self.assertIn("3", line)
        self.assertIn("2 bekleme", line)
        self.assertIn("4 sırada", line)

    def test_count_training_waiting_uses_next_attempt_bucket(self):
        from types import SimpleNamespace

        now = time.time()
        with (
            patch(
                "diplomacy_bot.fleet_metrics.scoped_list_accounts",
                return_value=[SimpleNamespace(name="w1"), SimpleNamespace(name="w2")],
            ),
            patch(
                "diplomacy_bot.fleet_metrics.load_health_state",
                return_value={
                    "training_watch_next_attempt": {
                        "w1": now + 60,
                        "w2": now - 60,
                        "other": now + 60,
                    }
                },
            ),
        ):
            self.assertEqual(count_fleet_training_waiting(42), 1)

    def test_count_actions_since(self):
        import sqlite3

        from diplomacy_bot.action_log_query import count_actions_since

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            with sqlite3.connect(db) as c:
                c.execute(
                    """
                    CREATE TABLE action_log (
                        account_name TEXT, telegram_user_id INT, action TEXT,
                        result TEXT, success INT, created_at REAL
                    )
                    """
                )
                now = time.time()
                c.execute(
                    "INSERT INTO action_log VALUES (?,?,?,?,?,?)",
                    ("ygt", 1, "autofarm", "ok", 1, now - 100),
                )
                c.execute(
                    "INSERT INTO action_log VALUES (?,?,?,?,?,?)",
                    ("ygt", 1, "autofarm", "fail", 0, now - 100),
                )
            with patch("diplomacy_bot.action_log_query.DB_PATH", db):
                n = count_actions_since(
                    account_names=["ygt"],
                    action="autofarm",
                    since_unix=now - 3600,
                )
            self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
