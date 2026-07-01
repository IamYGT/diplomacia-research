"""Worker autofarm tick — telegram'dan bağımsız (M5)."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


def run_autofarm_tick(*, interval_sec: float) -> tuple[int, int]:
    """Due hesaplarda tick_one çalıştır. Dönüş: (ok, total_attempted)."""
    from diplomacy_bot.account_config import get_config, normalize_role
    from diplomacy_bot.account_pool import load_rules
    from diplomacy_bot.autofarm_notify import tick_is_token_error
    from diplomacy_bot.autofarm_delivery import send_autofarm_result_sync, send_token_recovery_sync
    from diplomacy_bot.config import AUTOFARM_INTERVAL_SEC, AUTOFARM_WORKER_ONLY
    from diplomacy_bot.fleet_manager import tick_one
    from diplomacy_bot.store import autofarm_due, log_action

    sec = interval_sec or AUTOFARM_INTERVAL_SEC
    due = list(autofarm_due(sec))
    if not due:
        return 0, 0

    rules = load_rules()
    ok = 0
    attempted = 0
    for i, acc in enumerate(due):
        if normalize_role(get_config(acc.name).role) == "off":
            continue
        if i > 0:
            time.sleep(rules.stagger_farm_sec)
        attempted += 1
        try:
            r = tick_one(acc)
            if tick_is_token_error(r):
                send_token_recovery_sync(acc)
                log_action(
                    "worker_autofarm",
                    account_name=acc.name,
                    telegram_user_id=acc.telegram_user_id,
                    result=f"token_invalid err={r.error or ''}"[:120],
                    success=False,
                )
                continue
            success = bool(r.ok)
            log_action(
                "worker_autofarm",
                account_name=acc.name,
                telegram_user_id=acc.telegram_user_id,
                result=f"ok={r.ok} bal={getattr(r, 'balance_after', 0)} err={r.error or ''}"[:120],
                success=success,
            )
            if AUTOFARM_WORKER_ONLY:
                send_autofarm_result_sync(acc, r)
            if r.ok:
                ok += 1
        except Exception as e:
            log.warning("worker autofarm %s: %s", acc.name, e)
    if attempted:
        log.info("worker: autofarm %s/%s ok (due=%s)", ok, attempted, len(due))
    return ok, attempted
