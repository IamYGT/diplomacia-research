"""Hesap komutları — /accounts, /add, /remove (M11)."""

from __future__ import annotations

import html
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from diplomacy_bot.auth import default_account_name, resolve_account
from diplomacy_bot.config import MAX_ACCOUNTS_PER_USER
from diplomacy_bot.store import remove_account, upsert_session
from diplomacy_bot.telegram_helpers import (
    _default_account,
    _send_accounts_picker,
    _set_default_account,
    _uid,
    _user_accounts,
    user_required,
)
from diplomacy_bot.telegram_ui import connect_inline_markup, main_reply_keyboard

log = logging.getLogger(__name__)


@user_required
async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    await update.message.reply_text(f"Telegram user ID: `{uid}`", parse_mode="Markdown")


@user_required
async def cmd_setaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await update.message.reply_text(
            f"Varsayılan: `{_default_account(context, uid) or '—'}`",
            parse_mode="Markdown",
        )
        return
    name = context.args[0].lower()
    if not resolve_account(name, uid):
        await update.message.reply_text("Hesap bulunamadı veya senin değil.")
        return
    _set_default_account(context, uid, name)
    await update.message.reply_text(f"✅ Varsayılan hesap: *{name}*", parse_mode="Markdown")


@user_required
async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not _user_accounts(uid):
        await update.message.reply_text(
            "Henüz hesap yok. Bağlamak için /connect",
            reply_markup=connect_inline_markup(),
        )
        return
    await _send_accounts_picker(update, context)


@user_required
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await update.message.reply_text(
            "Kullanım:\n"
            "• <code>/connect</code> — ilk hesap\n"
            "• <code>/add takma_ad</code> — ek hesap, sonra JWT yapıştır",
            parse_mode="HTML",
        )
        return
    alias = context.args[0].lower()
    name = default_account_name(uid, alias)
    token = " ".join(context.args[1:]).strip()
    if not token:
        context.user_data["pending_add"] = name
        await update.message.reply_text(
            f"<b>{html.escape(alias)}</b> için JWT yapıştır (<code>eyJ…</code>).",
            parse_mode="HTML",
        )
        return
    from diplomacy_bot import telegram_app as ta

    await ta._save_account(update, name, token, uid=uid, context=context)


@user_required
async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await update.message.reply_text("/remove isim")
        return
    name = context.args[0].lower()
    if not resolve_account(name, uid):
        await update.message.reply_text("Hesap bulunamadı veya senin değil.")
        return
    if remove_account(name, telegram_user_id=uid):
        if context.user_data.get("default_account") == name:
            context.user_data.pop("default_account", None)
            upsert_session(uid, active_account="")
        from diplomacy_bot.store import log_action

        log_action("remove", account_name=name, telegram_user_id=uid)
        await update.message.reply_text("✅ Hesap bottan kaldırıldı.")
    else:
        await update.message.reply_text("Silinemedi.")


@user_required
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    name = (
        context.args[0].lower()
        if context.args and len(context.args) == 1
        else _default_account(context, uid)
    )
    acc = resolve_account(name, uid) if name else None
    if not acc:
        await update.message.reply_text(
            "Hesap yok. /connect",
            reply_markup=connect_inline_markup(),
        )
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    from diplomacy_bot.telegram_app import _send_dashboard

    await _send_dashboard(update, acc, context)
