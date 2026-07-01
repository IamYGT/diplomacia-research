"""Worker autofarm tick testleri (M5)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_run_autofarm_tick_empty():
    from diplomacy_bot.jobs.worker_autofarm import run_autofarm_tick

    with patch("diplomacy_bot.store.autofarm_due", return_value=[]):
        ok, attempted = run_autofarm_tick(interval_sec=60)
    assert ok == 0
    assert attempted == 0


def test_run_autofarm_tick_calls_tick_one():
    from diplomacy_bot.jobs.worker_autofarm import run_autofarm_tick
    from diplomacy_bot.modules.orchestrator import TickResult
    from diplomacy_bot.store import Account

    acc = Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="YGT",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )
    tick = TickResult(account_name="ygt", ok=True, balance_after=100)

    with (
        patch("diplomacy_bot.store.autofarm_due", return_value=[acc]),
        patch("diplomacy_bot.account_config.get_config") as gc,
        patch("diplomacy_bot.account_config.normalize_role", return_value="farm"),
        patch("diplomacy_bot.account_pool.load_rules") as lr,
        patch("diplomacy_bot.fleet_manager.tick_one", return_value=tick) as t1,
        patch("diplomacy_bot.store.log_action"),
    ):
        gc.return_value = MagicMock(role="farm")
        lr.return_value = MagicMock(stagger_farm_sec=0)
        ok, attempted = run_autofarm_tick(interval_sec=60)

    assert attempted == 1
    assert ok == 1
    t1.assert_called_once_with(acc)


def test_run_autofarm_tick_token_invalid_disables_autofarm():
    from diplomacy_bot.jobs.worker_autofarm import run_autofarm_tick
    from diplomacy_bot.modules.orchestrator import TickResult
    from diplomacy_bot.store import Account

    acc = Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="YGT",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )
    tick = TickResult(account_name="ygt", ok=False, error="401 Unauthorized token expired")

    with (
        patch("diplomacy_bot.store.autofarm_due", return_value=[acc]),
        patch("diplomacy_bot.account_config.get_config") as gc,
        patch("diplomacy_bot.account_config.normalize_role", return_value="farm"),
        patch("diplomacy_bot.account_pool.load_rules") as lr,
        patch("diplomacy_bot.fleet_manager.tick_one", return_value=tick),
        patch("diplomacy_bot.store.log_action"),
        patch("diplomacy_bot.autofarm_delivery.send_token_recovery_sync") as recovery,
    ):
        gc.return_value = MagicMock(role="farm")
        lr.return_value = MagicMock(stagger_farm_sec=0)
        ok, attempted = run_autofarm_tick(interval_sec=60)

    assert attempted == 1
    assert ok == 0
    recovery.assert_called_once_with(acc)
