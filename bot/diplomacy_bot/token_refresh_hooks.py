"""Token otomatik yenileme — recovery öncesi sessiz deneme + /loginkaydet + /tokenauto."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .telegram_helpers import user_required

log = logging.getLogger(__name__)
_REGISTERED = False


@user_required
async def cmd_loginkaydet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta
    from .account_credentials import save_login
    from .auth import resolve_account

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    args = context.args or []
    if len(args) < 2:
        await msg.reply_text(
            "Kullanım: <code>/loginkaydet email@ornek.com şifren</code>\n\n"
            "Bilgiler şifreli saklanır — token süresi dolmadan bot otomatik yeniler.\n"
            "Cloudflare Turnstile engeli varsa konsol token'ını\n"
            "<code>data/token_inbox/hesap.jwt</code> dosyasına yaz.\n\n"
            "⚠️ Şifreyi komut satırına yazmak riskli — kayıttan sonra komut mesajını sil.",
            parse_mode="HTML",
        )
        return
    email = args[0]
    password = " ".join(args[1:])
    acc_name = ta._default_account(context, uid)
    if not acc_name:
        await msg.reply_text("Önce bir hesap bağla veya /setmain yap.")
        return
    acc = resolve_account(acc_name, uid)
    if not acc:
        await msg.reply_text("Hesap bulunamadı.")
        return
    save_login(acc.name, email, password)
    deleted = False
    if update.message:
        try:
            await update.message.delete()
            deleted = True
        except Exception as e:
            log.debug("loginkaydet delete failed: %s", e)
    warn = (
        ""
        if deleted
        else "\n\n⚠️ <b>Şifre sohbet geçmişinde kaldı</b> — komut mesajını hemen sil."
    )
    await msg.reply_text(
        f"✅ <b>{acc.name}</b> için giriş bilgisi kaydedildi.\n"
        "Token ~7 gün dolmadan önce otomatik yenilenecek."
        f"{warn}",
        parse_mode="HTML",
    )


@user_required
async def cmd_tokenauto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta
    from .account_config import get_config, update_config_field
    from .auth import resolve_account

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    acc_name = ta._default_account(context, uid)
    if not acc_name:
        await msg.reply_text("Önce hesap bağla.")
        return
    acc = resolve_account(acc_name, uid)
    if not acc:
        await msg.reply_text("Hesap bulunamadı.")
        return
    arg = (context.args[0].lower() if context.args else "").strip()
    cfg = get_config(acc.name)
    if arg in ("on", "aç", "ac", "1", "true"):
        update_config_field(acc.name, auto_token_refresh=True)
        await msg.reply_text(
            f"🔄 <b>{acc.name}</b> — otomatik token yenileme <b>açık</b>.",
            parse_mode="HTML",
        )
        return
    if arg in ("off", "kapat", "0", "false"):
        update_config_field(acc.name, auto_token_refresh=False)
        await msg.reply_text(
            f"⏸ <b>{acc.name}</b> — otomatik token yenileme <b>kapalı</b>.\n"
            "Manuel token yapıştırman gerekir.",
            parse_mode="HTML",
        )
        return
    state = "açık" if cfg.auto_token_refresh else "kapalı"
    await msg.reply_text(
        f"🔑 <b>{acc.name}</b> otomatik token yenileme: <b>{state}</b>\n\n"
        "<code>/tokenauto on</code> veya <code>/tokenauto off</code>",
        parse_mode="HTML",
    )


def register_token_refresh_handlers(application: Application) -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    application.add_handler(CommandHandler("loginkaydet", cmd_loginkaydet))
    application.add_handler(CommandHandler("tokenauto", cmd_tokenauto))
    _REGISTERED = True
    log.info("/loginkaydet ve /tokenauto komutları kayıtlı")


def patch_silent_refresh_before_recovery() -> None:
    from . import token_recovery_hooks as trh

    if getattr(trh, "_silent_refresh_patched", False):
        return

    _orig = trh.maybe_auto_token_recovery

    async def maybe_auto_token_recovery(update, context, acc, snap):
        from .token_recovery import is_token_auth_error
        from .token_refresh_service import try_silent_refresh

        err = str((snap or {}).get("error") or "")
        if is_token_auth_error(err):
            key = f"silent_refresh_tried_{acc.name}"
            if not context.user_data.get(key):
                context.user_data[key] = True
                if await asyncio.to_thread(try_silent_refresh, acc):
                    context.user_data.pop(f"token_recovery_sent_{acc.name}", None)
                    msg = update.effective_message
                    if msg:
                        await msg.reply_text(
                            f"🔄 <b>{acc.name}</b> token'ı otomatik yenilendi.",
                            parse_mode="HTML",
                        )
                    from . import telegram_app as ta

                    await ta._open_dashboard_tracked(
                        update, context, acc, force_refresh=True
                    )
                    return
        await _orig(update, context, acc, snap)

    trh.maybe_auto_token_recovery = maybe_auto_token_recovery
    trh._silent_refresh_patched = True


def install_token_refresh_hooks() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_token_refresh_hooks_installed", False):
        return

    patch_silent_refresh_before_recovery()
    from .token_refresh_job import install_token_refresh_job

    install_token_refresh_job()

    _orig_post = ta._post_init

    async def _post_init(application: Application) -> None:
        await _orig_post(application)
        register_token_refresh_handlers(application)

    ta._post_init = _post_init
    ta._token_refresh_hooks_installed = True
    log.info("token_refresh hook'ları kuruldu")
