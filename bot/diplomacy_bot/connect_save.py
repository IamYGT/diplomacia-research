"""Hesap bağlama — token kaydet, mesaj gönder, dashboard aç."""

from __future__ import annotations

import asyncio
import html
import logging
from typing import TYPE_CHECKING, Any

from telegram import Update

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

log = logging.getLogger(__name__)


async def save_account_connected(
    update: Update,
    name: str,
    token: str,
    *,
    uid: int,
    context: "ContextTypes.DEFAULT_TYPE | None" = None,
) -> None:
    """Token doğrula, DB'ye yaz, farm ipuçlu başarı mesajı + dashboard."""
    from . import telegram_app as ta
    from .account_runtime import account_context
    from .auth import resolve_account
    from .config import MAX_ACCOUNTS_PER_USER
    from .connect_intel import format_account_connected_html
    from .game_api import get_profile
    from .store import add_account, count_accounts_for_user, proxy_assignments, suggest_proxy
    from .telegram_ui import main_reply_keyboard

    msg = update.effective_message
    if not msg:
        return

    try:
        existing = resolve_account(name, uid)
        if count_accounts_for_user(uid) >= MAX_ACCOUNTS_PER_USER and not existing:
            await msg.reply_text(f"❌ En fazla {MAX_ACCOUNTS_PER_USER} hesap ekleyebilirsin.")
            return

        slot = suggest_proxy(proxy_assignments())

        def _fetch():
            with account_context(proxy_id=slot.id, proxy_url=slot.url or None):
                return get_profile(token)

        prof = await asyncio.to_thread(_fetch)
        acc = add_account(
            name,
            token,
            prof.player_id,
            prof.username,
            slot.id,
            slot.url,
            telegram_user_id=uid,
        )
        if context is not None:
            ta._set_default_account(context, uid, acc.name)
            ta._set_pending_connect(context, uid, False)
            context.user_data.pop("pending_add", None)
        ta.log_action(
            "connect",
            account_name=acc.name,
            telegram_user_id=uid,
            result=f"{prof.username} lv{prof.level}",
        )
        await msg.reply_text(
            format_account_connected_html(acc.name, prof, telegram_user_id=uid),
            parse_mode="HTML",
            reply_markup=main_reply_keyboard(),
        )
        if context is not None and acc:
            await ta._send_dashboard(update, acc, context)
    except Exception as e:
        from .token_recovery import is_token_auth_error

        if context is not None and is_token_auth_error(str(e)):
            from .token_recovery_hooks import send_token_recovery_flow

            ta.log_action(
                "connect",
                account_name=name,
                telegram_user_id=uid,
                result=str(e)[:200],
                success=False,
            )
            await send_token_recovery_flow(update, context, name, uid=uid)
            return
        ta.log_action(
            "connect",
            account_name=name,
            telegram_user_id=uid,
            result=str(e)[:200],
            success=False,
        )
        await msg.reply_text(f"❌ {html.escape(str(e))}", parse_mode="HTML")
        log.warning("connect_save failed name=%s: %s", name, e)


def wire_save_account() -> None:
    """Tek _save_account zinciri: klavye ctx + connect_save (token recovery içeride)."""
    from . import telegram_app as ta

    if getattr(ta, "_save_account_wired", False):
        return

    async def _save_account(update, name, token, *, uid=None, context=None):
        from .keyboard_reply import user_reply_keyboard

        real_uid = uid or ta._uid(update)
        async with user_reply_keyboard(real_uid):
            await save_account_connected(
                update, name, token, uid=real_uid, context=context
            )

    ta._save_account = _save_account
    ta._save_account_wired = True
    log.info("connect_save wire_save_account kuruldu")
