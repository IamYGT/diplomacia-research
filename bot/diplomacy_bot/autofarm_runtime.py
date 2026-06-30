"""Autofarm job — zengin bildirim + token recovery (runtime patch)."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

from .autofarm_notify import (
    format_autofarm_message,
    format_autofarm_token_recovery_intro,
    should_send_recovery_for_account,
    tick_is_token_error,
)
from .token_recovery import console_script_for_user, token_recovery_markup

log = logging.getLogger(__name__)


async def send_token_recovery_via_bot(
    bot,
    chat_id: int,
    account_name: str,
    *,
    telegram_user_id: int,
    intro: str | None = None,
) -> None:
    from .session_token_pending import set_pending_token_account

    set_pending_token_account(telegram_user_id, account_name)
    body = intro or (
        f"<b>🔑 Token yenileme</b>\n\n"
        f"Hesap: <b>{account_name}</b>\n"
        "Adımlar aşağıda — <code>eyJ…</code> token'ı buraya yapıştır."
    )
    await bot.send_message(
        chat_id=chat_id,
        text=body,
        parse_mode="HTML",
        reply_markup=token_recovery_markup(account_name),
        disable_web_page_preview=True,
    )
    await bot.send_message(chat_id=chat_id, text=console_script_for_user())
    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"⏳ <b>Token bekleniyor</b> — <code>eyJ…</code> yapıştır.\n"
            f"Hesap: <b>{account_name}</b>"
        ),
        parse_mode="HTML",
    )


async def handle_autofarm_token_error(context: ContextTypes.DEFAULT_TYPE, acc) -> None:
    from .store import set_autofarm, set_runtime_state

    notify_uid = acc.telegram_user_id
    if not notify_uid:
        return
    set_autofarm(acc.name, False)
    set_runtime_state(acc.name, "token_invalid")
    if not should_send_recovery_for_account(acc.name):
        return
    try:
        await send_token_recovery_via_bot(
            context.bot,
            notify_uid,
            acc.name,
            telegram_user_id=notify_uid,
            intro=format_autofarm_token_recovery_intro(acc),
        )
        log.info("Autofarm token recovery gönderildi acc=%s uid=%s", acc.name, notify_uid)
    except Exception as e:
        log.warning("Autofarm token recovery fail acc=%s: %s", acc.name, e)


def install_autofarm_notify_patch() -> None:
    from . import telegram_app as ta
    from .account_config import get_config, normalize_role
    from .account_pool import load_rules
    from .config import AUTOFARM_INTERVAL_SEC, TELEGRAM_ADMIN_IDS
    from .fleet_manager import tick_one
    from .store import autofarm_due, log_action

    if getattr(ta, "_autofarm_notify_patched", False):
        return

    _orig = ta.autofarm_job

    async def autofarm_job_patched(context: ContextTypes.DEFAULT_TYPE) -> None:
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
                msg = format_autofarm_message(acc, r)
                notify_uid = acc.telegram_user_id or (
                    next(iter(TELEGRAM_ADMIN_IDS)) if TELEGRAM_ADMIN_IDS else None
                )
                if msg and notify_uid:
                    await context.bot.send_message(
                        chat_id=notify_uid,
                        text=msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
            except Exception as e:
                log.exception("autofarm %s: %s", acc.name, e)
                from .crash_notify import send_crash_notify

                send_crash_notify(
                    f"Autofarm hatası ({acc.name})",
                    str(e)[:500],
                    exc=e,
                    dedupe_key=f"autofarm:{acc.name}:{type(e).__name__}",
                )

    ta.autofarm_job = autofarm_job_patched
    ta._autofarm_notify_patched = True
    log.info("Autofarm zengin bildirim + token recovery patch kuruldu")
