"""Mission farm economy regression tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.modules.mission_types import MissionPhase, MissionPlan, MissionRuntime, PhaseSpec


class MissionFarmEconomyTests(unittest.TestCase):
    def test_farm_phase_prepares_pills_before_work(self):
        from diplomacy_bot.modules.mission_executor import run_mission_step

        calls: list[str] = []
        cfg = SimpleNamespace(craft_pills_when_low=True)
        plan = MissionPlan("m1", "w1", [PhaseSpec(MissionPhase.FARM_TICK)])
        rt = MissionRuntime("m1", "w1", plan)

        def ensure_pills(token, cfg, *, _api):
            calls.append("ensure")
            return {"crafted": 20}

        def run_work(token, cfg, *, _api):
            calls.append("work")
            return {"ok": True, "earned": {"money": 7}}

        with (
            patch("diplomacy_bot.modules.mission_executor.travel.is_traveling", return_value=False),
            patch("diplomacy_bot.modules.mission_executor.economy.ensure_pills", side_effect=ensure_pills),
            patch("diplomacy_bot.modules.mission_executor.factory.run_work_cycle", side_effect=run_work),
            patch("diplomacy_bot.modules.mission_executor.clear_mission"),
            patch("diplomacy_bot.store.set_runtime_state"),
            patch("diplomacy_bot.tick_activity.record_mission_step"),
        ):
            result = run_mission_step("tok", rt, cfg=cfg, _api=MagicMock())

        self.assertTrue(result.ok)
        self.assertEqual(calls, ["ensure", "work"])
        self.assertEqual(result.actions[0], {"economy": {"crafted": 20}})
        self.assertEqual(result.actions[1]["farm"]["earned"]["money"], 7)


if __name__ == "__main__":
    unittest.main()
