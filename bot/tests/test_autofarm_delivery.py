"""Autofarm delivery testleri (M7)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _acc():
    from diplomacy_bot.store import Account

    return Account(
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
        telegram_user_id=515491882,
    )


def test_send_token_recovery_sync_sets_state_and_notifies():
    from diplomacy_bot.autofarm_delivery import send_token_recovery_sync

    acc = _acc()
    with (
        patch("diplomacy_bot.store.set_autofarm") as sa,
        patch("diplomacy_bot.store.set_runtime_state") as srs,
        patch("diplomacy_bot.autofarm_notify.should_send_recovery_for_account", return_value=True),
        patch("diplomacy_bot.session_token_pending.set_pending_token_account") as pending,
        patch("diplomacy_bot.autofarm_delivery.send_telegram_message", return_value=True) as send,
    ):
        ok = send_token_recovery_sync(acc)

    assert ok is True
    sa.assert_called_once_with("ygt", False)
    srs.assert_called_once_with("ygt", "token_invalid")
    pending.assert_called_once_with(515491882, "ygt")
    assert send.call_count >= 3


def test_send_autofarm_result_sync_success():
    from diplomacy_bot.autofarm_delivery import send_autofarm_result_sync
    from diplomacy_bot.modules.orchestrator import TickResult

    acc = _acc()
    r = TickResult(account_name="ygt", ok=True, balance_after=5000, earned_money=100)
    with patch("diplomacy_bot.autofarm_delivery.send_telegram_message", return_value=True) as send:
        ok = send_autofarm_result_sync(acc, r)
    assert ok is True
    send.assert_called_once()
    assert "Otomatik tur" in send.call_args[0][1]


def test_worker_tick_notifies_when_worker_only():
    from diplomacy_bot.jobs.worker_autofarm import run_autofarm_tick
    from diplomacy_bot.modules.orchestrator import TickResult

    acc = _acc()
    tick = TickResult(account_name="ygt", ok=True, balance_after=100, earned_money=50)

    with (
        patch("diplomacy_bot.store.autofarm_due", return_value=[acc]),
        patch("diplomacy_bot.account_config.get_config") as gc,
        patch("diplomacy_bot.account_config.normalize_role", return_value="farm"),
        patch("diplomacy_bot.account_pool.load_rules") as lr,
        patch("diplomacy_bot.fleet_manager.tick_one", return_value=tick),
        patch("diplomacy_bot.store.log_action"),
        patch("diplomacy_bot.config.AUTOFARM_WORKER_ONLY", True),
        patch("diplomacy_bot.autofarm_delivery.send_autofarm_result_sync", return_value=True) as notify,
    ):
        gc.return_value = MagicMock(role="farm")
        lr.return_value = MagicMock(stagger_farm_sec=0)
        ok, attempted = run_autofarm_tick(interval_sec=60)

    assert attempted == 1
    assert ok == 1
    notify.assert_called_once_with(acc, tick)


def test_runtime_token_error_delegates_to_delivery():
    import asyncio
    from unittest.mock import MagicMock

    from diplomacy_bot.jobs.autofarm_telegram_job import handle_autofarm_token_error

    acc = _acc()
    ctx = MagicMock()
    with patch(
        "diplomacy_bot.jobs.autofarm_telegram_job.send_token_recovery_sync",
        return_value=True,
    ) as recovery:
        asyncio.run(handle_autofarm_token_error(ctx, acc))
    recovery.assert_called_once_with(acc)


def test_autofarm_telegram_job_skips_when_worker_only():
    import asyncio
    from unittest.mock import MagicMock

    from diplomacy_bot.jobs.autofarm_telegram_job import run_autofarm_telegram_job

    ctx = MagicMock()
    with (
        patch("diplomacy_bot.config.AUTOFARM_WORKER_ONLY", True),
        patch("diplomacy_bot.store.autofarm_due") as due,
    ):
        asyncio.run(run_autofarm_telegram_job(ctx))
    due.assert_not_called()
