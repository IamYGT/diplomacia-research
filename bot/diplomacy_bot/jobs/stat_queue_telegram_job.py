"""Telegram PTB stat queue job (M9)."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

log = logging.getLogger(__name__)


async def run_stat_queue_telegram_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    from diplomacy_bot.stat_queue import accounts_for_stat_queue, tick_stat_queue

    for acc in accounts_for_stat_queue():
        try:
            await asyncio.to_thread(tick_stat_queue, acc)
        except Exception as e:
            log.exception("stat_queue %s: %s", acc.name, e)
