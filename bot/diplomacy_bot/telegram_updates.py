"""Güncellemeler komutu — telegram_app'e dokunmadan kayıt."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .bot_updates import format_updates_html, updates_inline_markup, format_version_short_html
from .telegram_helpers import user_required

log = logging.getLogger(__name__)

_REGISTERED = False


@user_required
async def cmd_guncellemeler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    page = 0
    if context.args and context.args[0].isdigit():
        page = max(0, int(context.args[0]) - 1)
    await update.message.reply_text(
        format_updates_html(page=page),
        parse_mode="HTML",
        reply_markup=updates_inline_markup(page),
    )


@user_required
async def cmd_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_guncellemeler(update, context)


def register_bot_commands_extra() -> None:
    """BOT_COMMANDS listesine güncellemeler ekler (post_init'te set_my_commands öncesi)."""
    from telegram import BotCommand
    from . import telegram_ui as ui

    extra = [
        BotCommand("guncellemeler", "Sürüm notları ve yenilikler"),
        BotCommand("version", "Sürüm özeti"),
    ]
    seen = {c.command for c in ui.BOT_COMMANDS}
    for cmd in extra:
        if cmd.command not in seen:
            ui.BOT_COMMANDS.append(cmd)


def register_updates_handlers(application: Application) -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    for name, handler in (
        ("guncellemeler", cmd_guncellemeler),
        ("updates", cmd_updates),
    ):
        application.add_handler(CommandHandler(name, handler))
    _REGISTERED = True
    log.info("Güncellemeler komutları kayıtlı: /guncellemeler, /updates")


async def handle_updates_callback(data: str, query) -> bool:
    """callbacks.py veya feature_handlers üzerinden: updates:page:N"""
    if not data.startswith("updates:"):
        return False
    if not query or not query.message:
        return False
    page = 0
    if data.startswith("updates:page:"):
        try:
            page = int(data.split(":")[-1])
        except ValueError:
            page = 0
    bot = query.get_bot()
    await bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=format_updates_html(page=page),
        parse_mode="HTML",
        reply_markup=updates_inline_markup(page),
    )
    return True


def install_updates_post_init() -> None:
    """telegram_app._post_init + callbacks + extras menü — tek hook."""
    from . import telegram_app as ta

    if getattr(ta, "_updates_hook_installed", False):
        return

    _orig_post = ta._post_init

    async def _post_init(application: Application) -> None:
        register_bot_commands_extra()
        await _orig_post(application)
        register_updates_handlers(application)

    ta._post_init = _post_init

    _orig_version = ta.cmd_version

    @user_required
    async def cmd_version_patched(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            format_version_short_html(),
            parse_mode="HTML",
            reply_markup=updates_inline_markup(0),
        )

    ta.cmd_version = cmd_version_patched

    from . import callbacks as cb

    _orig_cb = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if data == "menu:updates":
            await open_updates_panel(query)
            return
        if await handle_updates_callback(data, query):
            return
        return await _orig_cb(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched

    from . import telegram_ui as ui

    _orig_extras = ui.extras_inline_markup

    def extras_inline_markup_patched(snap=None):
        markup = _orig_extras(snap)
        rows = list(markup.inline_keyboard)
        rows.append([InlineKeyboardButton("📋 Güncellemeler", callback_data="menu:updates")])
        return InlineKeyboardMarkup(rows)

    ui.extras_inline_markup = extras_inline_markup_patched

    ta._updates_hook_installed = True
    log.info("Güncellemeler hook kuruldu: komut, callback, extras menü")


async def open_updates_panel(query) -> None:
    if not query or not query.message:
        return
    bot = query.get_bot()
    await bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=format_updates_html(page=0),
        parse_mode="HTML",
        reply_markup=updates_inline_markup(0),
    )
