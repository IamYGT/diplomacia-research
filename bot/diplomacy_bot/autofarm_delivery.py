"""Autofarm Telegram teslimatı — tek kaynak (worker HTTP + bot job)."""

from __future__ import annotations

import html
import logging

from .event_notify import send_telegram_message
from .modules.orchestrator import TickResult
from .store import Account

log = logging.getLogger(__name__)


def resolve_notify_chat_id(acc: Account) -> int | None:
    from .config import TELEGRAM_ADMIN_IDS

    if acc.telegram_user_id:
        return int(acc.telegram_user_id)
    if TELEGRAM_ADMIN_IDS:
        return next(iter(TELEGRAM_ADMIN_IDS))
    return None


def token_recovery_markup_dict(account_name: str) -> dict:
    name = account_name.strip().lower()
    return {
        "inline_keyboard": [
            [
                {"text": "🔗 Oyuna git", "url": "https://diplomacia.com.tr/"},
                {"text": "📋 Konsol kodu", "callback_data": f"connect:recover:{name}"},
            ],
            [{"text": "🏠 Ana Sayfa", "callback_data": "dash:home"}],
        ]
    }


def send_token_recovery_sync(acc: Account) -> bool:
    """Token hatası — autofarm kapat + recovery mesajları (sync HTTP)."""
    from .autofarm_notify import format_autofarm_token_recovery_intro, should_send_recovery_for_account
    from .session_token_pending import set_pending_token_account
    from .store import set_autofarm, set_runtime_state
    from .token_recovery import console_script_for_user

    notify_uid = resolve_notify_chat_id(acc)
    set_autofarm(acc.name, False)
    set_runtime_state(acc.name, "token_invalid")
    if not notify_uid:
        log.warning("autofarm delivery: token invalid %s — chat_id yok", acc.name)
        return False
    if not should_send_recovery_for_account(acc.name):
        return True
    set_pending_token_account(notify_uid, acc.name)
    ok = send_telegram_message(
        notify_uid,
        format_autofarm_token_recovery_intro(acc),
        reply_markup=token_recovery_markup_dict(acc.name),
    )
    send_telegram_message(notify_uid, console_script_for_user())
    send_telegram_message(
        notify_uid,
        (
            f"⏳ <b>Token bekleniyor</b> — <code>eyJ…</code> yapıştır.\n"
            f"Hesap: <b>{html.escape(acc.name)}</b>"
        ),
    )
    if ok:
        log.info("autofarm delivery: token recovery acc=%s uid=%s", acc.name, notify_uid)
    return ok


def send_autofarm_result_sync(acc: Account, r: TickResult) -> bool:
    """Farm tur sonucu — zengin HTML (sync HTTP)."""
    from .autofarm_notify import format_autofarm_message

    msg = format_autofarm_message(acc, r)
    notify_uid = resolve_notify_chat_id(acc)
    if not msg or not notify_uid:
        return False
    return send_telegram_message(notify_uid, msg)
