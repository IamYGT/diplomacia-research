"""Hesap seçici ekranı — accounts_picker doğrudan (stale import bypass)."""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from .account_balance import refresh_display_balances
from .accounts_picker import accounts_inline_markup, format_accounts_html
from .ui_tracker import edit_safe


async def send_accounts_picker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    edit: bool = False,
    page: int = 0,
) -> None:
    from .telegram_helpers import _default_account, _uid, _user_accounts

    uid = _uid(update)
    default = _default_account(context, uid) or "?"
    accs = _user_accounts(uid)
    balances = await asyncio.to_thread(refresh_display_balances, accs)
    text = format_accounts_html(default, accs, telegram_user_id=uid, balances=balances)
    markup = accounts_inline_markup(default, accs, telegram_user_id=uid, page=page)
    q = update.callback_query
    if edit and q and q.message:
        await edit_safe(
            q.get_bot(),
            q.message.chat_id,
            q.message.message_id,
            text,
            reply_markup=markup,
        )
        return
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=markup)
