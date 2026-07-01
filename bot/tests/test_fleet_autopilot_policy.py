#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_autopilot_policy import (
    FleetAutopilotPolicy,
    load_fleet_autopilot_policy,
    policy_from_region_args,
    save_fleet_autopilot_policy,
)


class FleetAutopilotPolicyTests(unittest.TestCase):
    def test_policy_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fleet_autopilot_policy.json"
            with patch("diplomacy_bot.fleet_autopilot_policy._STATE_PATH", path):
                save_fleet_autopilot_policy(
                    42,
                    FleetAutopilotPolicy(
                        province="Tahran",
                        vote=True,
                        province_vote=True,
                        candidate_id="cand-1",
                    ),
                )

                policy = load_fleet_autopilot_policy(42)

        self.assertEqual(policy.province, "Tahran")
        self.assertTrue(policy.vote)
        self.assertTrue(policy.province_vote)
        self.assertEqual(policy.candidate_id, "cand-1")

    def test_policy_from_region_args_keeps_optional_flags(self):
        policy = policy_from_region_args(
            "Hürmüz",
            {
                "vote": True,
                "province_vote": True,
                "candidate_id": "cand-1",
                "independent_citizenship": True,
                "visa_country_id": "country-2",
            },
        )

        self.assertEqual(policy.province, "Hürmüz")
        self.assertTrue(policy.vote)
        self.assertTrue(policy.province_vote)
        self.assertTrue(policy.independent_citizenship)
        self.assertEqual(policy.visa_country_id, "country-2")

    def test_start_autopilot_uses_saved_policy_when_no_args(self):
        from diplomacy_bot.fleet_mission_service import start_fleet_autopilot_for_uid

        policy = FleetAutopilotPolicy(province="Tahran", vote=True, province_vote=True)
        inbox = SimpleNamespace(ok=0, total=0, results=[])
        repair = SimpleNamespace(ok=1, total=1, results=[])
        mission = SimpleNamespace(fleet_id="region-1", batch=SimpleNamespace(ok=1, total=1, results=[]))
        with (
            patch("diplomacy_bot.fleet_autopilot_policy.load_fleet_autopilot_policy", return_value=policy),
            patch("diplomacy_bot.fleet_inbox_import.import_inbox_for_uid", return_value=inbox),
            patch("diplomacy_bot.fleet_autonomy_repair.repair_fleet_autonomy_for_uid", return_value=repair),
            patch(
                "diplomacy_bot.fleet_mission_service.enqueue_region_missions_for_uid",
                return_value=mission,
            ) as enqueue,
        ):
            result = start_fleet_autopilot_for_uid(42)

        self.assertEqual(result.province, "Tahran")
        self.assertTrue(enqueue.call_args.kwargs["vote"])
        self.assertTrue(enqueue.call_args.kwargs["province_vote"])
        self.assertEqual(enqueue.call_args.kwargs["province"], "Tahran")


class FleetStartCommandPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_fleetregion_command_uses_text_planner(self):
        from diplomacy_bot.domain.fleet_llm_decision import normalize_llm_decision
        from diplomacy_bot.fleet_region_hooks import cmd_fleetregion

        msg = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=42), effective_message=msg, message=msg)
        context = SimpleNamespace(args=["20", "hesabı", "Hürmüz'e", "çek", "oy", "ver"])
        mission = SimpleNamespace(
            fleet_id="region-1",
            phases=["assign_config", "travel_to_province", "election_vote", "farm_tick"],
            warnings=[],
            batch=SimpleNamespace(ok=1, total=1, results=[]),
        )

        def fake_planner(uid, args):
            decision = normalize_llm_decision({"province": "Hürmüz", "vote": True})
            return SimpleNamespace(province=decision.target.province, opts={"vote": decision.target.vote})

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fleet_autopilot_policy.json"
            with (
                patch("diplomacy_bot.fleet_autopilot_policy._STATE_PATH", path),
                patch("diplomacy_bot.telegram_helpers.bot_allows_user", return_value=True),
                patch("diplomacy_bot.telegram_app._uid", return_value=42),
                patch("diplomacy_bot.fleet_region_hooks.fleet_nav_inline_markup", return_value=None),
                patch("diplomacy_bot.fleet_region_hooks.resolve_fleet_start_plan", side_effect=fake_planner),
                patch("diplomacy_bot.fleet_mission_service.enqueue_region_missions_for_uid", return_value=mission) as enqueue,
            ):
                await cmd_fleetregion(update, context)
                policy = load_fleet_autopilot_policy(42)

        self.assertEqual(policy.province, "Hürmüz")
        self.assertTrue(policy.vote)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs["province"], "Hürmüz")
        self.assertTrue(enqueue.call_args.kwargs["vote"])
        update.effective_message.reply_text.assert_awaited_once()

    async def test_fleetstart_command_saves_target_policy_and_replies(self):
        from diplomacy_bot.fleet_region_hooks import cmd_fleetstart

        msg = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=42), effective_message=msg, message=msg)
        context = SimpleNamespace(args=["Tahran", "vote", "eyaletoy"])
        result = SimpleNamespace(
            province="Tahran",
            inbox=SimpleNamespace(ok=1, total=1, results=[]),
            repair=SimpleNamespace(ok=1, total=1),
            mission=SimpleNamespace(
                fleet_id="region-1",
                phases=["assign_config", "travel_to_province", "election_vote", "farm_tick"],
                warnings=[],
                batch=SimpleNamespace(ok=1, total=1, results=[]),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fleet_autopilot_policy.json"
            with (
                patch("diplomacy_bot.fleet_autopilot_policy._STATE_PATH", path),
                patch("diplomacy_bot.telegram_helpers.bot_allows_user", return_value=True),
                patch("diplomacy_bot.telegram_app._uid", return_value=42),
                patch("diplomacy_bot.fleet_region_hooks.fleet_nav_inline_markup", return_value=None),
                patch(
                    "diplomacy_bot.fleet_mission_service.start_fleet_autopilot_for_uid",
                    return_value=result,
                ) as start,
            ):
                await cmd_fleetstart(update, context)
                policy = load_fleet_autopilot_policy(42)

        self.assertEqual(policy.province, "Tahran")
        self.assertTrue(policy.vote)
        self.assertTrue(policy.province_vote)
        start.assert_called_once()
        self.assertTrue(start.call_args.kwargs["vote"])
        update.effective_message.reply_text.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
