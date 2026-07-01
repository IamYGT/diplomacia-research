"""Worker mission sweep tests."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WorkerMissionsTests(unittest.TestCase):
    def test_worker_missions_skips_future_wait(self):
        from diplomacy_bot.jobs.worker_missions import run_worker_missions_once

        acc = SimpleNamespace(name="w1", telegram_user_id=42)
        rt = SimpleNamespace(wait_until=time.time() + 3600)
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[acc]),
            patch("diplomacy_bot.mission_store.get_active_mission", return_value=rt),
            patch("diplomacy_bot.fleet_manager.tick_one") as tick,
        ):
            ok, attempted = run_worker_missions_once()

        self.assertEqual((ok, attempted), (0, 0))
        tick.assert_not_called()

    def test_worker_missions_ticks_due_mission(self):
        from diplomacy_bot.jobs.worker_missions import run_worker_missions_once

        acc = SimpleNamespace(name="w1", telegram_user_id=42)
        rt = SimpleNamespace(wait_until=time.time() - 1)
        result = SimpleNamespace(ok=True, error="")
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[acc]),
            patch("diplomacy_bot.mission_store.get_active_mission", return_value=rt),
            patch("diplomacy_bot.fleet_manager.tick_one", return_value=result) as tick,
            patch("diplomacy_bot.store.log_action") as log_action,
        ):
            ok, attempted = run_worker_missions_once()

        self.assertEqual((ok, attempted), (1, 1))
        tick.assert_called_once_with(acc)
        log_action.assert_called_once()

    def test_worker_missions_logs_exception_action(self):
        from diplomacy_bot.jobs.worker_missions import run_worker_missions_once

        acc = SimpleNamespace(name="w1", telegram_user_id=42)
        rt = SimpleNamespace(wait_until=time.time() - 1)
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[acc]),
            patch("diplomacy_bot.mission_store.get_active_mission", return_value=rt),
            patch("diplomacy_bot.fleet_manager.tick_one", side_effect=RuntimeError("boom")),
            patch("diplomacy_bot.store.log_action") as log_action,
        ):
            ok, attempted = run_worker_missions_once()

        self.assertEqual((ok, attempted), (0, 1))
        log_action.assert_called_once_with(
            "worker_mission_exception",
            account_name="w1",
            telegram_user_id=42,
            result="boom",
            success=False,
        )


if __name__ == "__main__":
    unittest.main()
