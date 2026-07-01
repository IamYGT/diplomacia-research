"""Onboarding komutları — /start, /connect (M10)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from diplomacy_bot.auth import resolve_account
from diplomacy_bot.config import GEMINI_API_KEY
from diplomacy_bot.telegram_helpers import (
    _default_account,
    _set_pending_connect,
    _uid,
    _user_accounts,
    user_required,
)
from diplomacy_bot.telegram_ui import (
    connect_inline_markup,
    format_token_guide_html,
    format_welcome_html,
    main_reply_keyboard,
)
from diplomacy_bot.token_console import format_console_script_telegram


async def send_connect_package(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    intro: str = "",
) -> None:
    msg = update.effective_message
    if not msg:
        return
    _set_pending_connect(context, _uid(update), True)
    await msg.reply_text(
        intro + format_token_guide_html(),
        parse_mode="HTML",
        reply_markup=connect_inline_markup(),
        disable_web_page_preview=True,
    )
    await msg.reply_text(format_console_script_telegram())


@user_required
async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    accs = _user_accounts(uid)
    intro = (
        "✅ Zaten bağlısın — yeni token gönderirsen hesap güncellenir.\n\n"
        if accs
        else ""
    )
    await send_connect_package(update, context, intro=intro)


@user_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    default = _default_account(context, uid)
    acc = resolve_account(default, uid) if default else None
    linked = acc is not None
    await update.message.reply_text(
        format_welcome_html(uid, default, gemini_ok=bool(GEMINI_API_KEY), linked=linked),
        parse_mode="HTML",
        reply_markup=main_reply_keyboard() if linked else connect_inline_markup(),
    )
    if acc:
        from diplomacy_bot.telegram_app import _send_dashboard

        await _send_dashboard(update, acc, context)
    elif not linked:
        _set_pending_connect(context, uid, True)
