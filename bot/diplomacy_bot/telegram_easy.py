"""Kolay mod — tek tuş program, savaş, klavye."""

from __future__ import annotations

import asyncio
import html
import logging

from telegram import BotCommand, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .account_runtime import interactive_account_context
from .auth import scoped_list_accounts
from .easy_mode import (
    format_program_status,
    format_program_step_message,
    program_hub_markup,
)
from .mission_store import clear_mission, enqueue_mission, get_active_mission
from .modules.mission_executor import run_mission_step
from .auth import resolve_account
from .store import get_account
from .telegram_helpers import user_required
from .war_contribute_format import enrich_war_contribute_pack, format_war_contribute_html_enhanced
from .war_ops import run_war_contribute

log = logging.getLogger(__name__)
_REGISTERED = False


def _resolve_account(name: str | None, uid: int):
    accs = scoped_list_accounts(uid)
    if not accs:
        return None, accs
    if name:
        acc = resolve_account(name.strip().lower(), uid)
        return acc, accs
    return accs[0], accs


async def _run_program_step(acc) -> tuple[str, InlineKeyboardMarkup | None]:
    rt = get_active_mission(acc.name)
    if not rt:
        rt = enqueue_mission(acc.name)

    def _step():
        with interactive_account_context(acc):
            fresh = get_active_mission(acc.name) or rt
            return run_mission_step(acc.token, fresh)

    step = await asyncio.to_thread(_step)
    status = format_program_status(get_active_mission(acc.name), account_name=acc.name)
    msg = format_program_step_message(step)
    return f"{msg}\n\n{status}", program_hub_markup(acc.name)


async def _run_war_contrib(acc) -> str:
    def _contrib():
        with interactive_account_context(acc):
            pack = run_war_contribute(acc.token, acc.name)
            return enrich_war_contribute_pack(pack, acc.name)

    pack = await asyncio.to_thread(_contrib)
    return format_war_contribute_html_enhanced(pack, pack.get("analysis"))


@user_required
async def cmd_kolay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else 0
    acc, _ = _resolve_account(None, uid)
    if not acc:
        await update.message.reply_text("Önce /connect ile hesabını bağla.")
        return
    rt = get_active_mission(acc.name)
    text = format_program_status(rt, account_name=acc.name)
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=program_hub_markup(acc.name),
    )


def register_easy_handlers(application: Application) -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    application.add_handler(CommandHandler("kolay", cmd_kolay))
    application.add_handler(CommandHandler("program", cmd_kolay))
    _REGISTERED = True
    log.info("Kolay mod: /kolay, /program")


def register_easy_commands_extra() -> None:
    from . import telegram_ui as ui

    extra = [
        BotCommand("kolay", "Büyük butonlu kolay menü"),
        BotCommand("program", "Günlük program (savaş+altın)"),
    ]
    seen = {c.command for c in ui.BOT_COMMANDS}
    for cmd in extra:
        if cmd.command not in seen:
            ui.BOT_COMMANDS.append(cmd)


async def handle_easy_menu_action(action: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Klavye: savaşa vur / programı çalıştır — AI'ya gitmeden."""
    uid = update.effective_user.id if update.effective_user else 0
    acc, _ = _resolve_account(None, uid)
    if not acc:
        await update.message.reply_text("Önce /connect ile hesabını bağla.")
        return True

    if action == "savaşa vur":
        from .easy_role import war_ui_enabled

        if not war_ui_enabled(acc.name):
            await update.message.reply_text(
                "🌾 Bu hesap <b>farm</b> modunda — savaş kapalı.\n\n"
                "Savaş sekmesinden listeyi görebilirsin; katkı için "
                f"<code>/setrole {html.escape(acc.name)} war</code> veya <code>hybrid</code>.",
                parse_mode="HTML",
            )
            return True
        msg = await _run_war_contrib(acc)
        await update.message.reply_text(msg, parse_mode="HTML")
        return True

    if action == "programı çalıştır":
        text, markup = await _run_program_step(acc)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
        return True

    if action == "programı durdur":
        clear_mission(acc.name)
        await update.message.reply_text(
            "🛑 Program durduruldu.\n\nTekrar başlamak için «Programı Çalıştır» butonuna bas.",
        )
        return True

    if action == "war_tab":
        from .telegram_tabs import open_tab_from_message

        await open_tab_from_message(update, acc, "war")
        return True

    if action == "travel_tab":
        from .telegram_tabs import open_tab_from_message

        await open_tab_from_message(update, acc, "travel")
        return True

    return False


async def handle_easy_callback(data: str, query, uid: int) -> bool:
    from .telegram_onboarding import handle_onboarding_callback

    if await handle_onboarding_callback(data, query, uid=uid):
        return True
    if not data.startswith("easy:"):
        return False
    if not query or not query.message:
        return False

    parts = data.split(":")
    if len(parts) < 2:
        return False
    op = parts[1]
    name = parts[2].lower() if len(parts) > 2 else ""
    acc, _ = _resolve_account(name or None, uid)
    if not acc:
        await query.answer("Hesap bulunamadı", show_alert=True)
        return True

    if op == "hub":
        rt = get_active_mission(acc.name)
        await query.edit_message_text(
            format_program_status(rt, account_name=acc.name),
            parse_mode="HTML",
            reply_markup=program_hub_markup(acc.name),
        )
        return True

    if op == "stop":
        clear_mission(acc.name)
        await query.edit_message_text(
            "🛑 Program durduruldu.",
            reply_markup=program_hub_markup(acc.name),
        )
        return True

    if op == "start":
        enqueue_mission(acc.name)
        text, markup = await _run_program_step(acc)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        return True

    if op == "run":
        from .store import set_autofarm

        if not acc.autofarm:
            set_autofarm(acc.name, True)
        if not get_active_mission(acc.name):
            enqueue_mission(acc.name)
        text, markup = await _run_program_step(acc)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        return True

    if op == "war":
        from .easy_role import war_ui_enabled

        if not war_ui_enabled(acc.name):
            await query.answer("Farm hesabı — savaş kapalı", show_alert=True)
            return True
        msg = await _run_war_contrib(acc)
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=program_hub_markup(acc.name),
        )
        return True

    return False
