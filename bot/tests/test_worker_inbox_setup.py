"""Worker inbox auto-setup tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WorkerInboxSetupTests(unittest.TestCase):
    def test_worker_inbox_setup_runs_autopilot_for_fresh_candidates(self):
        from diplomacy_bot.jobs.worker_inbox_setup import run_worker_inbox_setup_once
        from diplomacy_bot.fleet_command import FleetBatchResult, FleetOpResult

        result = MagicMock()
        result.inbox = FleetBatchResult()
        result.inbox.add(FleetOpResult("w1", True, "bağlandı"))
        result.inbox.add(FleetOpResult("w2", True, "bağlandı"))
        token_watch = ModuleType("diplomacy_bot.token_watch")
        token_watch.list_inbox_operator_uids = MagicMock(return_value=[42])
        token_watch.list_inbox_import_candidates = MagicMock(return_value=[("w1", "tok1"), ("w2", "tok2")])
        processed = ModuleType("diplomacy_bot.inbox_processed_state")
        processed.is_inbox_processed = MagicMock(return_value=False)
        processed.mark_inbox_processed = MagicMock()
        mission_service = ModuleType("diplomacy_bot.fleet_mission_service")
        mission_service.start_fleet_autopilot_for_uid = MagicMock(return_value=result)
        with patch.dict(
            sys.modules,
            {
                "diplomacy_bot.token_watch": token_watch,
                "diplomacy_bot.inbox_processed_state": processed,
                "diplomacy_bot.fleet_mission_service": mission_service,
            },
        ):
            uids, imported = run_worker_inbox_setup_once()

        self.assertEqual((uids, imported), (1, 2))
        mission_service.start_fleet_autopilot_for_uid.assert_called_once_with(42)
        processed.mark_inbox_processed.assert_called_once()
        marked = processed.mark_inbox_processed.call_args.args[0]
        self.assertEqual(marked, {"42:w1", "42:w2"})

    def test_worker_inbox_setup_keeps_failed_candidates_retryable(self):
        from diplomacy_bot.jobs.worker_inbox_setup import run_worker_inbox_setup_once
        from diplomacy_bot.fleet_command import FleetBatchResult, FleetOpResult

        result = MagicMock()
        result.inbox = FleetBatchResult()
        result.inbox.add(FleetOpResult("w1", False, "expired"))
        token_watch = ModuleType("diplomacy_bot.token_watch")
        token_watch.list_inbox_operator_uids = MagicMock(return_value=[42])
        token_watch.list_inbox_import_candidates = MagicMock(return_value=[("w1", "tok1")])
        processed = ModuleType("diplomacy_bot.inbox_processed_state")
        processed.is_inbox_processed = MagicMock(return_value=False)
        processed.mark_inbox_processed = MagicMock()
        mission_service = ModuleType("diplomacy_bot.fleet_mission_service")
        mission_service.start_fleet_autopilot_for_uid = MagicMock(return_value=result)
        with patch.dict(
            sys.modules,
            {
                "diplomacy_bot.token_watch": token_watch,
                "diplomacy_bot.inbox_processed_state": processed,
                "diplomacy_bot.fleet_mission_service": mission_service,
            },
        ):
            uids, imported = run_worker_inbox_setup_once()

        self.assertEqual((uids, imported), (1, 0))
        processed.mark_inbox_processed.assert_not_called()

    def test_worker_main_runs_inbox_when_enabled_before_training(self):
        from diplomacy_bot.jobs import worker_main

        refresh_mod = ModuleType("diplomacy_bot.token_refresh_service")
        refresh_mod.run_refresh_cycle = lambda: []
        calls = []
        with (
            patch.dict(sys.modules, {"diplomacy_bot.token_refresh_service": refresh_mod}),
            patch("diplomacy_bot.config.FLEET_INBOX_AUTO_SETUP", True),
            patch(
                "diplomacy_bot.jobs.worker_inbox_setup.run_worker_inbox_setup_once",
                side_effect=lambda: calls.append("inbox"),
            ),
            patch(
                "diplomacy_bot.jobs.worker_missions.run_worker_missions_once",
                side_effect=lambda: calls.append("missions"),
            ),
            patch(
                "diplomacy_bot.jobs.worker_stat_queue.run_worker_stat_queue_once",
                side_effect=lambda: calls.append("stat"),
            ),
            patch("diplomacy_bot.jobs.worker_training.run_training_tick", side_effect=lambda: calls.append("training")),
            patch(
                "diplomacy_bot.jobs.worker_autofarm.run_autofarm_tick",
                side_effect=lambda interval_sec: calls.append("autofarm"),
            ),
        ):
            worker_main._tick()

        self.assertEqual(calls[:5], ["inbox", "missions", "stat", "training", "autofarm"])


if __name__ == "__main__":
    unittest.main()
