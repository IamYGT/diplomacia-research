"""Görev komutları — sade Türkçe, büyük butonlar."""

from __future__ import annotations

import asyncio
import logging

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .auth import scoped_list_accounts
from .easy_mode import format_program_status, program_hub_markup
from .mission_store import clear_mission, enqueue_mission, get_active_mission
from .modules.mission_executor import run_mission_step
from .auth import resolve_account
from .store import get_account
from .telegram_easy import _run_program_step
from .telegram_helpers import user_required
from .telegram_navigation import reply_or_edit_callback
from .war_commands import resolve_and_configure_war

log = logging.getLogger(__name__)
_REGISTERED = False


@user_required
async def cmd_mission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else 0
    accs = scoped_list_accounts(uid)
    if not accs:
        await update.message.reply_text("Önce /connect ile hesabını bağla.")
        return

    args = context.args or []
    if not args:
        lines = ["<b>📋 Programlar</b>\n"]
        for a in accs[:8]:
            rt = get_active_mission(a.name)
            if rt:
                lines.append(f"• <b>{a.name}</b> — çalışıyor")
            else:
                lines.append(f"• {a.name} — boşta")
        lines.append("\nBaşlatmak için: <b>/kolay</b> veya «Programı Çalıştır» butonu")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=program_hub_markup(accs[0].name),
        )
        return

    sub = args[0].lower()
    if sub in ("cancel", "iptal", "durdur"):
        name = (args[1] if len(args) > 1 else accs[0].name).lower()
        if not resolve_account(name, uid):
            await update.message.reply_text("❌ Bu hesap sana ait değil.")
            return
        clear_mission(name)
        await update.message.reply_text(f"🛑 {name} programı durduruldu.")
        return

    if sub in ("new", "baslat", "başlat") and len(args) > 1:
        text = " ".join(args[1:])
        acc = accs[0]
        war_id = None
        war_label = None

        def _resolve():
            from .account_runtime import interactive_account_context

            with interactive_account_context(acc):
                return resolve_and_configure_war(acc.token, acc.name, text)

        r = await asyncio.to_thread(_resolve)
        if r.get("ok"):
            war_id = r.get("war_id")
            war_label = r.get("summary")
        enqueue_mission(acc.name, target_war_id=war_id, war_label=war_label)
        text_out, markup = await _run_program_step(acc)
        await update.message.reply_text(text_out, parse_mode="HTML", reply_markup=markup)
        return

    await update.message.reply_text(
        "Kolay kullanım için /kolay yaz.\nVeya «Programı Çalıştır» butonuna bas.",
    )


@user_required
async def cmd_mission_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else 0
    accs = scoped_list_accounts(uid)
    if not accs:
        await update.message.reply_text("Hesap yok.")
        return
    name = (context.args[0] if context.args else accs[0].name).lower()
    if not resolve_account(name, uid):
        await update.message.reply_text("❌ Bu hesap sana ait değil.")
        return
    clear_mission(name)
    await update.message.reply_text(f"🛑 {name} programı durduruldu.")


def register_mission_handlers(application: Application) -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    application.add_handler(CommandHandler("mission", cmd_mission))
    application.add_handler(CommandHandler("gorev", cmd_mission))
    application.add_handler(CommandHandler("mission_cancel", cmd_mission_cancel))
    _REGISTERED = True
    log.info("Görev komutları: /mission, /gorev, /mission_cancel")


def register_mission_commands_extra() -> None:
    from . import telegram_ui as ui

    extra = [
        BotCommand("setmain", "Ana hesabı değiştir"),
    ]
    seen = {c.command for c in ui.BOT_COMMANDS}
    for cmd in extra:
        if cmd.command not in seen:
            ui.BOT_COMMANDS.append(cmd)


async def handle_mission_callback(data: str, query, uid: int) -> bool:
    if not data.startswith("mission:"):
        return False
    if data == "mission:new":
        accs = scoped_list_accounts(uid)
        if accs:
            await query.message.reply_text(
                "Program başlatmak için /kolay yaz\nveya «Programı Çalıştır» butonuna bas.",
                reply_markup=program_hub_markup(accs[0].name),
            )
        return True
    if data == "mission:cancel":
        accs = scoped_list_accounts(uid)
        if accs:
            clear_mission(accs[0].name)
        await reply_or_edit_callback(query, data, "🛑 Program durduruldu.")
        return True
    if data.startswith("mission:step:"):
        name = data.split(":", 2)[-1].lower()
        acc = resolve_account(name, uid)
        if not acc:
            await query.answer("Hesap yok", show_alert=True)
            return True
        from .telegram_easy import _run_program_step

        text, markup = await _run_program_step(acc)
        await reply_or_edit_callback(query, data, text, parse_mode="HTML", reply_markup=markup)
        return True
    return False
