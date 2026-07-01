"""Ana hesap Telegram komutları."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .account_main import get_main_account_name, set_main_account
from .auth import resolve_account, scoped_list_accounts
from .telegram_helpers import _set_default_account, user_required

log = logging.getLogger(__name__)
_REGISTERED = False


@user_required
async def cmd_setmain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else 0
    accs = scoped_list_accounts(uid)
    if not accs:
        await update.message.reply_text("Önce hesap ekle.")
        return
    if not context.args:
        main = get_main_account_name(uid) or "?"
        names = ", ".join(a.name for a in accs[:10])
        await update.message.reply_text(
            f"👑 Ana hesap: <b>{main}</b>\n\nDeğiştirmek için:\n<code>/setmain hesap_adı</code>\n\nHesaplar: {names}",
            parse_mode="HTML",
        )
        return
    name = context.args[0].strip().lower()
    if not resolve_account(name, uid):
        await update.message.reply_text(f"❌ `{name}` bulunamadı veya senin değil.", parse_mode="Markdown")
        return
    set_main_account(name, telegram_user_id=uid)
    _set_default_account(context, uid, name)
    await update.message.reply_text(
        f"✅ Ana hesap: <b>{name}</b>\n<i>Dashboard ve komutlar bu hesaba geçti.</i>",
        parse_mode="HTML",
    )


@user_required
async def cmd_anahesap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_setmain(update, context)


def register_account_handlers(application: Application) -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    application.add_handler(CommandHandler("setmain", cmd_setmain))
    application.add_handler(CommandHandler("anahesap", cmd_anahesap))
    _REGISTERED = True
    log.info("Hesap komutları: /setmain, /anahesap")
