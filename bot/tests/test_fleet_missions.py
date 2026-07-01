"""Durable fleet mission tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.domain.fleet_missions import (
    FleetMissionTarget,
    build_aod_phase_dicts,
    build_region_phase_dicts,
)
from diplomacy_bot.modules.mission_types import MissionPhase, MissionPlan, MissionRuntime, PhaseSpec


class FleetMissionTests(unittest.TestCase):
    def test_aod_phase_dicts_include_setup_travel_residence_farm(self):
        phases = build_aod_phase_dicts(
            FleetMissionTarget(role="hybrid", factory_id="fid", province="Hürmüz", fleet_id="f1")
        )
        self.assertEqual(
            [p["phase"] for p in phases],
            ["assign_config", "travel_to_province", "residence_set", "farm_tick"],
        )
        self.assertEqual(phases[0]["params"]["factory_id"], "fid")

    def test_mission_store_roundtrips_new_phase(self):
        from diplomacy_bot.mission_store import _plan_from_json, _plan_to_json

        plan = MissionPlan(
            "m1",
            "w1",
            [
                PhaseSpec(MissionPhase.ASSIGN_CONFIG, params={"factory_id": "fid"}),
                PhaseSpec(MissionPhase.ELECTION_VOTE, params={"candidate_id": "c1"}),
            ],
        )
        back = _plan_from_json(_plan_to_json(plan))
        self.assertEqual(back.phases[0].phase, MissionPhase.ASSIGN_CONFIG)
        self.assertEqual(back.phases[0].params["factory_id"], "fid")
        self.assertEqual(back.phases[1].phase, MissionPhase.ELECTION_VOTE)

    def test_region_phase_dicts_include_optional_politics(self):
        phases = build_region_phase_dicts(
            FleetMissionTarget(
                factory_id="fid",
                province="Hürmüz",
                citizenship_country_id="c-tr",
                visa_country_id="v-ir",
                vote=True,
                candidate_id="cand-1",
            )
        )
        self.assertEqual(
            [p["phase"] for p in phases],
            [
                "assign_config",
                "travel_to_province",
                "residence_set",
                "citizenship_apply",
                "visa_apply",
                "election_vote",
                "farm_tick",
            ],
        )

    def test_assign_config_phase_enables_fixed_autofarm(self):
        from diplomacy_bot.modules.mission_executor import run_mission_step

        plan = MissionPlan(
            "m1",
            "w1",
            [
                PhaseSpec(MissionPhase.ASSIGN_CONFIG, params={"role": "hybrid", "factory_id": "fid"}),
                PhaseSpec(MissionPhase.FARM_TICK),
            ],
        )
        rt = MissionRuntime("m1", "w1", plan)
        with (
            patch("diplomacy_bot.modules.mission_executor.update_config_field") as update_cfg,
            patch("diplomacy_bot.store.set_autofarm") as set_auto,
            patch("diplomacy_bot.modules.mission_executor.save_mission_runtime"),
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            r = run_mission_step("tok", rt, cfg=SimpleNamespace(), _api=MagicMock())

        self.assertTrue(r.ok)
        self.assertEqual(rt.phase_index, 1)
        kwargs = update_cfg.call_args.kwargs
        self.assertEqual(kwargs["work_mode"], "fixed")
        self.assertEqual(kwargs["preferred_factory_id"], "fid")
        set_auto.assert_called_once_with("w1", True)

    def test_travel_phase_waits_when_travel_started(self):
        from diplomacy_bot.modules.mission_executor import run_mission_step

        plan = MissionPlan("m1", "w1", [PhaseSpec(MissionPhase.TRAVEL_TO_PROVINCE, params={"province": "Hürmüz"})])
        rt = MissionRuntime("m1", "w1", plan)
        with (
            patch(
                "diplomacy_bot.modules.mission_executor.travel.ensure_in_province",
                return_value={"ok": True, "traveling": True, "remaining_ms": 120000},
            ),
            patch("diplomacy_bot.modules.mission_executor.save_mission_runtime"),
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            r = run_mission_step("tok", rt, cfg=SimpleNamespace(), _api=MagicMock())

        self.assertTrue(r.blocked)
        self.assertEqual(r.wait_ms, 120000)

    def test_vote_phase_finishes_when_no_active_candidate(self):
        from diplomacy_bot.modules.mission_executor import run_mission_step

        plan = MissionPlan("m1", "w1", [PhaseSpec(MissionPhase.ELECTION_VOTE)])
        rt = MissionRuntime("m1", "w1", plan)

        def mock_api(method, path, token, body=None, delay=0):
            if path == "/elections/active":
                return 200, {"elections": []}
            return 404, {"error": "no"}

        with (
            patch("diplomacy_bot.modules.mission_executor.clear_mission") as clear,
            patch("diplomacy_bot.store.set_runtime_state"),
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            r = run_mission_step("tok", rt, cfg=SimpleNamespace(), _api=mock_api)

        self.assertTrue(r.ok)
        self.assertTrue(r.mission_complete)
        clear.assert_called_once_with("w1", status="completed")

    def test_enqueue_aod_missions_skips_main_and_writes_workers(self):
        from diplomacy_bot.fleet_mission_service import enqueue_aod_missions_for_uid

        main = SimpleNamespace(name="main")
        worker = SimpleNamespace(name="w1")
        with (
            patch("diplomacy_bot.fleet_mission_service.resolve_operator_factory", return_value=("fid", "Hürmüz", "")),
            patch("diplomacy_bot.account_main.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.auth.scoped_list_accounts", return_value=[main, worker]),
            patch("diplomacy_bot.mission_store.enqueue_phase_plan") as enqueue,
        ):
            result = enqueue_aod_missions_for_uid(42)

        self.assertEqual(result.batch.ok, 1)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.args[0], "w1")

    def test_enqueue_region_missions_writes_optional_phase_plan(self):
        from diplomacy_bot.fleet_mission_service import enqueue_region_missions_for_uid

        main = SimpleNamespace(name="main")
        worker = SimpleNamespace(name="w1")
        with (
            patch("diplomacy_bot.fleet_mission_service.resolve_operator_factory", return_value=("fid", "Hürmüz", "")),
            patch("diplomacy_bot.account_main.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.auth.scoped_list_accounts", return_value=[main, worker]),
            patch("diplomacy_bot.mission_store.enqueue_phase_plan") as enqueue,
        ):
            result = enqueue_region_missions_for_uid(
                42,
                province="Tahran",
                citizenship_country_id="country-1",
                vote=True,
            )

        self.assertEqual(result.batch.ok, 1)
        phases = enqueue.call_args.args[1]
        self.assertIn("citizenship_apply", [p["phase"] for p in phases])
        self.assertIn("election_vote", [p["phase"] for p in phases])


if __name__ == "__main__":
    unittest.main()
