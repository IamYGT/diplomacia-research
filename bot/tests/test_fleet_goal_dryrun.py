#!/usr/bin/env python3
"""High-level dry run for the 20-account fleet autonomy goal."""

from __future__ import annotations

import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_autonomy_audit import audit_fleet_autonomy
from diplomacy_bot.fleet_autonomy_repair import repair_fleet_autonomy_for_uid
from diplomacy_bot.fleet_mission_service import (
    enqueue_aod_missions_for_uid,
    enqueue_region_missions_for_uid,
)
from diplomacy_bot.store import Account


def _acc(name: str, *, uid: int = 42, autofarm: bool = True) -> Account:
    return Account(
        id=1,
        name=name,
        token="tok",
        player_id=name,
        username=name,
        autofarm=autofarm,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=uid,
    )


def _ready_cfg() -> SimpleNamespace:
    return SimpleNamespace(
        role="hybrid",
        stat_auto_enabled=True,
        training_enabled=True,
        craft_pills_when_low=True,
        auto_travel_enabled=True,
        auto_token_refresh=True,
        preferred_factory_id="factory-uuid",
        work_mode="fixed",
    )


class FleetGoalDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.main = _acc("main")
        self.workers = [_acc(f"w{i:02d}") for i in range(1, 21)]
        self.accounts = [self.main, *self.workers]

    def test_repair_then_audit_marks_twenty_workers_ready(self):
        with (
            patch(
                "diplomacy_bot.fleet_autonomy_repair.resolve_operator_factory",
                return_value=("factory-uuid", "Hürmüz", ""),
            ),
            patch("diplomacy_bot.fleet_autonomy_repair.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.fleet_autonomy_repair.scoped_list_accounts", return_value=self.accounts),
            patch("diplomacy_bot.fleet_autonomy_repair.set_autofarm") as set_auto,
            patch("diplomacy_bot.fleet_autonomy_repair.update_config_field") as update_cfg,
        ):
            repair = repair_fleet_autonomy_for_uid(42)

        self.assertEqual((repair.ok, repair.total), (20, 20))
        self.assertEqual(set_auto.call_count, 20)
        self.assertNotIn("main", [c.args[0] for c in set_auto.call_args_list])
        self.assertEqual(update_cfg.call_count, 20)
        for call in update_cfg.call_args_list:
            self.assertEqual(call.kwargs["role"], "hybrid")
            self.assertEqual(call.kwargs["work_mode"], "fixed")
            self.assertEqual(call.kwargs["preferred_factory_id"], "factory-uuid")
            self.assertTrue(call.kwargs["stat_auto_enabled"])
            self.assertTrue(call.kwargs["training_enabled"])
            self.assertTrue(call.kwargs["craft_pills_when_low"])
            self.assertTrue(call.kwargs["auto_travel_enabled"])
            self.assertTrue(call.kwargs["auto_token_refresh"])

        with (
            patch("diplomacy_bot.fleet_autonomy_audit.get_config", return_value=_ready_cfg()),
            patch("diplomacy_bot.fleet_autonomy_audit.load_token_refresh_sources") as sources,
        ):
            audit = audit_fleet_autonomy(
                self.accounts,
                factory_id="factory-uuid",
                main_account_name="main",
            )

        self.assertEqual((audit.ready, audit.total), (20, 20))
        self.assertEqual(audit.blockers, [])
        sources.assert_called_once()

    def test_aod_region_and_training_dry_run_cover_twenty_workers(self):
        with (
            patch(
                "diplomacy_bot.fleet_mission_service.resolve_operator_factory",
                return_value=("factory-uuid", "Hürmüz", ""),
            ),
            patch("diplomacy_bot.account_main.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.auth.scoped_list_accounts", return_value=self.accounts),
            patch("diplomacy_bot.mission_store.enqueue_phase_plan") as enqueue,
        ):
            aod = enqueue_aod_missions_for_uid(42, province="Hürmüz")
            self.assertEqual((aod.batch.ok, aod.batch.total), (20, 20))
            self.assertEqual(enqueue.call_count, 20)
            self.assertEqual(enqueue.call_args_list[0].args[0], "w01")
            self.assertEqual(
                [p["phase"] for p in enqueue.call_args_list[0].args[1]],
                ["assign_config", "travel_to_province", "residence_set", "farm_tick"],
            )

            enqueue.reset_mock()
            region = enqueue_region_missions_for_uid(
                42,
                province="Hürmüz",
                citizenship_country_id="country-1",
                visa_country_id="country-2",
                vote=True,
                candidate_id="candidate-1",
            )

        self.assertEqual((region.batch.ok, region.batch.total), (20, 20))
        self.assertEqual(enqueue.call_count, 20)
        region_phases = [p["phase"] for p in enqueue.call_args_list[-1].args[1]]
        self.assertIn("citizenship_apply", region_phases)
        self.assertIn("visa_apply", region_phases)
        self.assertIn("election_vote", region_phases)

        from diplomacy_bot.jobs.worker_training import run_training_tick

        with (
            patch("diplomacy_bot.store.list_accounts", return_value=self.workers),
            patch("diplomacy_bot.account_config.get_config", return_value=_ready_cfg()),
            patch("diplomacy_bot.account_config.normalize_role", return_value="hybrid"),
            patch("diplomacy_bot.account_runtime.account_context", return_value=nullcontext()),
            patch("diplomacy_bot.modules.training.try_free_attack", return_value={"ok": True}) as attack,
            patch("diplomacy_bot.jobs.worker_training._load_last_attacks", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._load_next_attempts", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._save_attack_ts") as save_attack,
            patch("diplomacy_bot.store.log_action") as log_action,
        ):
            ok, checked = run_training_tick(min_interval_sec=0)

        self.assertEqual((ok, checked), (20, 20))
        self.assertEqual(attack.call_count, 20)
        self.assertEqual(save_attack.call_count, 20)
        self.assertEqual(log_action.call_count, 20)


if __name__ == "__main__":
    unittest.main()
