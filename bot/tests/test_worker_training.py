"""Worker training sidecar tests."""

from __future__ import annotations

import unittest
from contextlib import nullcontext
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _acc(name: str = "w1"):
    from diplomacy_bot.store import Account

    return Account(
        id=1,
        name=name,
        token="tok",
        player_id="p1",
        username="W1",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=42,
    )


class WorkerTrainingTests(unittest.TestCase):
    def test_training_tick_attacks_ready_account(self):
        from diplomacy_bot.jobs.worker_training import run_training_tick

        cfg = SimpleNamespace(role="hybrid", training_enabled=True)
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[_acc()]),
            patch("diplomacy_bot.account_config.get_config", return_value=cfg),
            patch("diplomacy_bot.account_config.normalize_role", return_value="hybrid"),
            patch("diplomacy_bot.account_runtime.account_context", return_value=nullcontext()),
            patch("diplomacy_bot.modules.training.try_free_attack", return_value={"ok": True}) as attack,
            patch("diplomacy_bot.jobs.worker_training._load_last_attacks", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._load_next_attempts", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._save_attack_ts") as save_ts,
            patch("diplomacy_bot.store.log_action") as log_action,
        ):
            ok, checked = run_training_tick(min_interval_sec=0)

        self.assertEqual((ok, checked), (1, 1))
        attack.assert_called_once()
        save_ts.assert_called_once_with("w1")
        log_action.assert_called_once()

    def test_training_tick_skips_recent_attack(self):
        import time

        from diplomacy_bot.jobs.worker_training import run_training_tick

        cfg = SimpleNamespace(role="hybrid", training_enabled=True)
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[_acc()]),
            patch("diplomacy_bot.account_config.get_config", return_value=cfg),
            patch("diplomacy_bot.account_config.normalize_role", return_value="hybrid"),
            patch("diplomacy_bot.modules.training.try_free_attack") as attack,
            patch("diplomacy_bot.jobs.worker_training._load_last_attacks", return_value={"w1": time.time()}),
            patch("diplomacy_bot.jobs.worker_training._load_next_attempts", return_value={}),
        ):
            ok, checked = run_training_tick(min_interval_sec=3300)

        self.assertEqual((ok, checked), (0, 0))
        attack.assert_not_called()

    def test_training_tick_skips_until_next_attempt_due(self):
        import time

        from diplomacy_bot.jobs.worker_training import run_training_tick

        cfg = SimpleNamespace(role="hybrid", training_enabled=True)
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[_acc()]),
            patch("diplomacy_bot.account_config.get_config", return_value=cfg),
            patch("diplomacy_bot.account_config.normalize_role", return_value="hybrid"),
            patch("diplomacy_bot.modules.training.try_free_attack") as attack,
            patch("diplomacy_bot.jobs.worker_training._load_last_attacks", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._load_next_attempts", return_value={"w1": time.time() + 300}),
        ):
            ok, checked = run_training_tick()

        self.assertEqual((ok, checked), (0, 0))
        attack.assert_not_called()

    def test_training_tick_schedules_cooldown_retry_without_counting_success(self):
        from diplomacy_bot.jobs.worker_training import run_training_tick

        cfg = SimpleNamespace(role="hybrid", training_enabled=True)
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[_acc()]),
            patch("diplomacy_bot.account_config.get_config", return_value=cfg),
            patch("diplomacy_bot.account_config.normalize_role", return_value="hybrid"),
            patch("diplomacy_bot.account_runtime.account_context", return_value=nullcontext()),
            patch(
                "diplomacy_bot.modules.training.try_free_attack",
                return_value={"skipped": "free_attack_cooldown", "ms": 120000},
            ),
            patch("diplomacy_bot.jobs.worker_training._load_last_attacks", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._load_next_attempts", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._save_next_attempt_ts") as save_next,
            patch("diplomacy_bot.jobs.worker_training._save_attack_ts") as save_attack,
            patch("diplomacy_bot.store.log_action") as log_action,
        ):
            ok, checked = run_training_tick()

        self.assertEqual((ok, checked), (0, 1))
        save_next.assert_called_once()
        self.assertEqual(save_next.call_args.args[0], "w1")
        save_attack.assert_not_called()
        log_action.assert_called_once()
        self.assertEqual(log_action.call_args.args[0], "training_skip")
        self.assertEqual(log_action.call_args.kwargs["result"], "free_attack_cooldown")
        self.assertFalse(log_action.call_args.kwargs["success"])

    def test_training_tick_logs_no_training_war_skip(self):
        from diplomacy_bot.jobs.worker_training import run_training_tick

        cfg = SimpleNamespace(role="hybrid", training_enabled=True)
        with (
            patch("diplomacy_bot.store.list_accounts", return_value=[_acc()]),
            patch("diplomacy_bot.account_config.get_config", return_value=cfg),
            patch("diplomacy_bot.account_config.normalize_role", return_value="hybrid"),
            patch("diplomacy_bot.account_runtime.account_context", return_value=nullcontext()),
            patch(
                "diplomacy_bot.modules.training.try_free_attack",
                return_value={"skipped": "no_training_war"},
            ),
            patch("diplomacy_bot.jobs.worker_training._load_last_attacks", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._load_next_attempts", return_value={}),
            patch("diplomacy_bot.jobs.worker_training._save_next_attempt_ts"),
            patch("diplomacy_bot.store.log_action") as log_action,
        ):
            ok, checked = run_training_tick()

        self.assertEqual((ok, checked), (0, 1))
        log_action.assert_called_once()
        self.assertEqual(log_action.call_args.args[0], "training_skip")
        self.assertEqual(log_action.call_args.kwargs["result"], "no_training_war")

    def test_worker_main_runs_training_sidecar_before_autofarm(self):
        from diplomacy_bot.jobs import worker_main

        calls = []
        refresh_mod = ModuleType("diplomacy_bot.token_refresh_service")
        refresh_mod.run_refresh_cycle = lambda: []
        with (
            patch.dict(sys.modules, {"diplomacy_bot.token_refresh_service": refresh_mod}),
            patch("diplomacy_bot.jobs.worker_missions.run_worker_missions_once", return_value=(0, 0)),
            patch("diplomacy_bot.jobs.worker_stat_queue.run_worker_stat_queue_once", return_value=(0, 0)),
            patch("diplomacy_bot.jobs.worker_training.run_training_tick", side_effect=lambda: calls.append("training")),
            patch(
                "diplomacy_bot.jobs.worker_autofarm.run_autofarm_tick",
                side_effect=lambda interval_sec: calls.append("autofarm"),
            ),
        ):
            worker_main._tick()

        self.assertEqual(calls[:2], ["training", "autofarm"])


if __name__ == "__main__":
    unittest.main()
