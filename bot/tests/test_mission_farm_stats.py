"""Mission farm phase stat automation tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.modules.mission_types import MissionPhase, MissionPlan, MissionRuntime, PhaseSpec


class MissionFarmStatsTests(unittest.TestCase):
    def test_farm_phase_runs_stat_automation_before_and_after_work(self):
        from diplomacy_bot.modules.mission_executor import run_mission_step

        plan = MissionPlan("m1", "w1", [PhaseSpec(MissionPhase.FARM_TICK)])
        rt = MissionRuntime("m1", "w1", plan)
        stat_results = [
            {"passive": [{"ok": True}], "upgrades": [{"ok": True, "skill": "kisla"}]},
            {"passive": [{"ok": True, "post": True}], "upgrades": [{"ok": True, "skill": "ekonomi"}]},
        ]
        with (
            patch("diplomacy_bot.modules.mission_executor.travel.is_traveling", return_value=False),
            patch("diplomacy_bot.modules.mission_executor.economy.ensure_pills", return_value=None),
            patch("diplomacy_bot.modules.mission_executor.factory.run_work_cycle", return_value={"ok": True}),
            patch("diplomacy_bot.modules.mission_stats.stats.run_stat_automation", side_effect=stat_results),
            patch("diplomacy_bot.modules.mission_executor.clear_mission"),
            patch("diplomacy_bot.store.set_runtime_state"),
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            r = run_mission_step("tok", rt, cfg=SimpleNamespace(stat_auto_enabled=True), _api=MagicMock())

        self.assertTrue(r.ok)
        self.assertIn({"passive_stats": [{"ok": True}]}, r.actions)
        self.assertIn({"stat_upgrades": [{"ok": True, "skill": "kisla"}]}, r.actions)
        self.assertIn({"passive_stats_post": [{"ok": True, "post": True}]}, r.actions)
        self.assertIn({"stat_upgrades_post": [{"ok": True, "skill": "ekonomi"}]}, r.actions)


if __name__ == "__main__":
    unittest.main()
