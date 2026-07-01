"""Worker mission sweep — bekleyen/aktif account_missions ilerletir."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


def run_worker_missions_once() -> tuple[int, int]:
    """Due mission hesaplarını tick_one ile ilerlet. Dönüş: (ok, attempted)."""
    from diplomacy_bot.fleet_manager import tick_one
    from diplomacy_bot.mission_store import get_active_mission
    from diplomacy_bot.store import list_accounts, log_action

    ok = 0
    attempted = 0
    now = time.time()
    for acc in list_accounts():
        rt = get_active_mission(acc.name)
        if not rt:
            continue
        if rt.wait_until and rt.wait_until > now:
            continue
        attempted += 1
        try:
            r = tick_one(acc)
            success = bool(r.ok)
            if success:
                ok += 1
            log_action(
                "worker_mission",
                account_name=acc.name,
                telegram_user_id=acc.telegram_user_id or 0,
                result=f"ok={r.ok} err={r.error or ''}"[:120],
                success=success,
            )
        except Exception as e:
            log.warning("worker mission %s: %s", acc.name, e)
            log_action(
                "worker_mission_exception",
                account_name=acc.name,
                telegram_user_id=acc.telegram_user_id or 0,
                result=str(e)[:120],
                success=False,
            )
    if attempted:
        log.info("worker: missions %s/%s ok", ok, attempted)
    return ok, attempted
