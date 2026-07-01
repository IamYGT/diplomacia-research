"""Worker stat queue — telegram'dan bağımsız stat otomasyonu."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def run_worker_stat_queue_once() -> tuple[int, int]:
    """Stat queue hesaplarını tick eder. Dönüş: (changed, attempted)."""
    from diplomacy_bot.stat_queue import accounts_for_stat_queue, tick_stat_queue

    changed = 0
    attempted = 0
    for acc in accounts_for_stat_queue():
        attempted += 1
        try:
            result = tick_stat_queue(acc)
            if result:
                changed += 1
        except Exception as e:
            log.warning("worker stat_queue %s: %s", acc.name, e)
    if attempted:
        log.info("worker: stat_queue %s/%s changed", changed, attempted)
    return changed, attempted
