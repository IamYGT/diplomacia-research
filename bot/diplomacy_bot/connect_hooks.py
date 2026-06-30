"""Connect / token yapıştırma — çoklu hesap ve seyahat fast-path."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from .telegram_helpers import user_required

log = logging.getLogger(__name__)


def patch_connect_intro() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_connect_intro_patched", False):
        return

    _orig = ta.cmd_connect

    @user_required
    async def cmd_connect_patched(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = ta._uid(update)
        accs = ta._user_accounts(uid)
        if not accs:
            await _orig(update, context)
            return
        intro = (
            "✅ Zaten bağlısın.\n\n"
            "• <b>Aynı hesap</b> — token'ı direkt yapıştır (güncellenir)\n"
            "• <b>İkinci hesap</b> — önce <code>/add takma_ad</code> yaz, sonra token\n\n"
        )
        await ta._send_connect_package(update, context, intro=intro)

    ta.cmd_connect = cmd_connect_patched
    ta._connect_intro_patched = True


def patch_run_ai_travel_fast() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_run_ai_travel_patched", False):
        return

    _orig = ta._run_ai

    async def _run_ai_patched(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        uid = ta._uid(update)
        default = ta._default_account(context, uid)
        from .auth import resolve_account

        acc = resolve_account(default, uid) if default else None
        if acc:
            from .account_runtime import interactive_account_context
            from .intent_travel_fast import try_travel_fast_path

            def _travel():
                with interactive_account_context(acc):
                    return try_travel_fast_path(text, acc)

            travel = await asyncio.to_thread(_travel)
            if travel is not None:
                await ta._reply_long(
                    update,
                    travel.reply,
                    parse_mode=getattr(travel, "parse_mode", "Markdown"),
                    inline_buttons=travel.inline_buttons,
                )
                return
        await _orig(update, context, text)

    ta._run_ai = _run_ai_patched
    ta._run_ai_travel_patched = True
    log.info("Seyahat fast-path _run_ai patch kuruldu")


def install_connect_hooks() -> None:
    patch_connect_intro()
    patch_run_ai_travel_fast()
