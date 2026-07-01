"""PTB repeating jobs — bootstrap wiring (M9)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_telegram_ptb_jobs() -> None:
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.jobs.autofarm_telegram_job import run_autofarm_telegram_job
    from diplomacy_bot.jobs.press_like_telegram_job import run_press_like_telegram_job
    from diplomacy_bot.jobs.stat_queue_telegram_job import run_stat_queue_telegram_job

    if getattr(ta, "_ptb_jobs_wired", False):
        return
    ta.autofarm_job = run_autofarm_telegram_job
    ta.stat_queue_job = run_stat_queue_telegram_job
    ta.press_like_job = run_press_like_telegram_job
    ta._ptb_jobs_wired = True
    log.info("PTB jobs wired: autofarm, stat_queue, press_like")
