"""Mission region failure regression tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.modules.mission_executor import run_mission_step
from diplomacy_bot.modules.mission_types import MissionPhase, MissionPlan, MissionRuntime, PhaseSpec, PhaseStatus


def _runtime(phase: MissionPhase, params: dict | None = None) -> MissionRuntime:
    plan = MissionPlan("m1", "w1", [PhaseSpec(phase, params=params or {})])
    return MissionRuntime("m1", "w1", plan)


class MissionRegionFailureTests(unittest.TestCase):
    def test_citizenship_api_error_does_not_advance_phase(self):
        calls = []

        def mock_api(method, path, token, body=None, delay=0):
            calls.append((method, path, body))
            if path == "/citizenship/my":
                return 200, {"status": "none"}
            if path == "/citizenship/apply":
                return 400, {"error": "başvuru reddedildi"}
            return 404, {"error": "no"}

        rt = _runtime(MissionPhase.CITIZENSHIP_APPLY, {"country_id": "country-1"})
        with (
            patch("diplomacy_bot.modules.mission_executor.clear_mission") as clear,
            patch("diplomacy_bot.modules.mission_executor.save_mission_runtime") as save,
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            result = run_mission_step("tok", rt, cfg=SimpleNamespace(), _api=mock_api)

        self.assertFalse(result.ok)
        self.assertEqual(result.phase_status, PhaseStatus.FAILED)
        self.assertEqual(result.error, "başvuru reddedildi")
        self.assertEqual(rt.phase_index, 0)
        self.assertEqual(rt.last_error, "başvuru reddedildi")
        self.assertIn(("POST", "/citizenship/apply", {"to_country_id": "country-1", "reason": "Filo operasyonu"}), calls)
        save.assert_called_once_with(rt, status="active")
        clear.assert_not_called()

    def test_visa_api_error_does_not_advance_phase(self):
        def mock_api(method, path, token, body=None, delay=0):
            if path == "/visas/apply":
                return 409, {"message": "vize zaten bekliyor"}
            return 404, {"error": "no"}

        rt = _runtime(MissionPhase.VISA_APPLY, {"country_id": "country-1"})
        with (
            patch("diplomacy_bot.modules.mission_executor.clear_mission") as clear,
            patch("diplomacy_bot.modules.mission_executor.save_mission_runtime") as save,
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            result = run_mission_step("tok", rt, cfg=SimpleNamespace(), _api=mock_api)

        self.assertEqual(result.phase_status, PhaseStatus.FAILED)
        self.assertEqual(result.error, "vize zaten bekliyor")
        self.assertEqual(rt.phase_index, 0)
        save.assert_called_once_with(rt, status="active")
        clear.assert_not_called()

    def test_election_vote_api_error_does_not_advance_phase(self):
        def mock_api(method, path, token, body=None, delay=0):
            if path == "/elections/active":
                return 200, {"elections": [{"id": "e1", "candidates": [{"id": "cand-1"}]}]}
            if path == "/elections/vote":
                return 400, {"error": "sandık kapalı"}
            return 404, {"error": "no"}

        rt = _runtime(MissionPhase.ELECTION_VOTE, {"candidate_id": "cand-1"})
        with (
            patch("diplomacy_bot.modules.mission_executor.clear_mission") as clear,
            patch("diplomacy_bot.modules.mission_executor.save_mission_runtime") as save,
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            result = run_mission_step("tok", rt, cfg=SimpleNamespace(), _api=mock_api)

        self.assertFalse(result.ok)
        self.assertEqual(result.phase_status, PhaseStatus.FAILED)
        self.assertEqual(result.error, "sandık kapalı")
        self.assertEqual(rt.phase_index, 0)
        save.assert_called_once_with(rt, status="active")
        clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
