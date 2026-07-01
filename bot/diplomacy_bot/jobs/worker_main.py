"""Arka plan worker — autofarm + token refresh (M5)."""

from __future__ import annotations

import logging
import os
import time

log = logging.getLogger(__name__)

_TICK_SEC = float(os.environ.get("WORKER_TICK_SEC", "60"))


def run_worker_loop(*, once: bool = False) -> None:
    """PM2: diplomacy-worker — telegram'dan bağımsız."""
    from diplomacy_bot.bootstrap import install_bootstrap

    install_bootstrap()
    log.info("diplomacy-worker başladı tick=%ss", _TICK_SEC)
    while True:
        _tick()
        if once:
            break
        time.sleep(_TICK_SEC)


def _tick() -> None:
    from diplomacy_bot.config import AUTOFARM_INTERVAL_SEC, FLEET_INBOX_AUTO_SETUP
    from diplomacy_bot.jobs.worker_autofarm import run_autofarm_tick
    from diplomacy_bot.jobs.worker_inbox_setup import run_worker_inbox_setup_once
    from diplomacy_bot.jobs.worker_missions import run_worker_missions_once
    from diplomacy_bot.jobs.worker_training import run_training_tick

    if FLEET_INBOX_AUTO_SETUP:
        run_worker_inbox_setup_once()
    run_worker_missions_once()
    run_training_tick()
    run_autofarm_tick(interval_sec=AUTOFARM_INTERVAL_SEC)
    try:
        from diplomacy_bot.token_refresh_service import run_refresh_cycle

        results = run_refresh_cycle()
        ok = sum(1 for r in results if r.ok)
        if ok:
            log.info("worker: token refresh %s/%s", ok, len(results))
    except Exception as e:
        log.warning("worker token refresh: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker_loop(once="--once" in __import__("sys").argv)
