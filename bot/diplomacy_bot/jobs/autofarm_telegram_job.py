"""Telegram PTB autofarm job — explicit handler (M8, patch yok)."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

from diplomacy_bot.autofarm_delivery import send_autofarm_result_sync, send_token_recovery_sync
from diplomacy_bot.autofarm_notify import tick_is_token_error

log = logging.getLogger(__name__)


async def handle_autofarm_token_error(context: ContextTypes.DEFAULT_TYPE, acc) -> None:
    del context
    try:
        await asyncio.to_thread(send_token_recovery_sync, acc)
    except Exception as e:
        log.warning("Autofarm token recovery fail acc=%s: %s", acc.name, e)


async def run_autofarm_telegram_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    from diplomacy_bot.account_config import get_config, normalize_role
    from diplomacy_bot.account_pool import load_rules
    from diplomacy_bot.config import AUTOFARM_INTERVAL_SEC, AUTOFARM_WORKER_ONLY
    from diplomacy_bot.crash_notify import send_crash_notify
    from diplomacy_bot.fleet_manager import tick_one
    from diplomacy_bot.store import autofarm_due, log_action

    if AUTOFARM_WORKER_ONLY:
        return
    rules = load_rules()
    due = list(autofarm_due(AUTOFARM_INTERVAL_SEC))
    for i, acc in enumerate(due):
        if normalize_role(get_config(acc.name).role) == "off":
            continue
        if i > 0:
            await asyncio.sleep(rules.stagger_farm_sec)
        try:
            r = await asyncio.to_thread(tick_one, acc)
            log_action(
                "autofarm",
                account_name=acc.name,
                telegram_user_id=acc.telegram_user_id,
                result=f"ok={r.ok} balance={getattr(r, 'balance_after', 0)} err={r.error or ''}"[:120],
                success=bool(r.ok) and not tick_is_token_error(r),
            )
            if tick_is_token_error(r):
                await handle_autofarm_token_error(context, acc)
                continue
            await asyncio.to_thread(send_autofarm_result_sync, acc, r)
        except Exception as e:
            log.exception("autofarm %s: %s", acc.name, e)
            send_crash_notify(
                f"Autofarm hatası ({acc.name})",
                str(e)[:500],
                exc=e,
                dedupe_key=f"autofarm:{acc.name}:{type(e).__name__}",
            )
