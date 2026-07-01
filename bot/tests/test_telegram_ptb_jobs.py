"""PTB telegram job testleri (M9)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_stat_queue_job_ticks_accounts():
    from diplomacy_bot.jobs.stat_queue_telegram_job import run_stat_queue_telegram_job
    from diplomacy_bot.store import Account

    acc = Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="YGT",
        autofarm=False,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )
    ctx = MagicMock()
    with (
        patch(
            "diplomacy_bot.stat_queue.accounts_for_stat_queue",
            return_value=[acc],
        ),
        patch("diplomacy_bot.stat_queue.tick_stat_queue") as tick,
    ):
        asyncio.run(run_stat_queue_telegram_job(ctx))
    tick.assert_called_once_with(acc)
