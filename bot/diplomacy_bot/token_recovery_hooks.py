"""Token geçersiz — Telegram yeniden bağlanma hook'ları."""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .token_recovery import (
    console_script_for_user,
    format_token_recovery_html,
    is_token_auth_error,
    token_recovery_markup,
)

log = logging.getLogger(__name__)
_INSTALLED = False


def _mark_waiting(context: ContextTypes.DEFAULT_TYPE, uid: int, account_name: str) -> None:
    from .session_token_pending import set_pending_token_account
    from .telegram_helpers import _set_pending_connect

    context.user_data["pending_token_refresh"] = account_name.strip().lower()
    set_pending_token_account(uid, account_name)
    _set_pending_connect(context, uid, True)


async def send_token_recovery_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    account_name: str,
    *,
    uid: int | None = None,
) -> None:
    from . import telegram_app as ta

    uid = uid or ta._uid(update)
    _mark_waiting(context, uid, account_name)
    msg = update.effective_message
    if not msg and update.callback_query and update.callback_query.message:
        msg = update.callback_query.message
    if not msg:
        return
    await msg.reply_text(
        format_token_recovery_html(account_name),
        parse_mode="HTML",
        reply_markup=token_recovery_markup(account_name),
        disable_web_page_preview=True,
    )
    await msg.reply_text(console_script_for_user())
    await msg.reply_text(
        f"⏳ <b>Token bekleniyor</b> — <code>eyJ…</code> ile başlayan metni buraya yapıştır.\n"
        f"Hesap: <b>{account_name}</b>",
        parse_mode="HTML",
    )
    log.info("Token recovery flow uid=%s acc=%s", uid, account_name)


async def maybe_auto_token_recovery(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    acc,
    snap: dict | None,
) -> None:
    err = str((snap or {}).get("error") or "")
    if not is_token_auth_error(err):
        return
    key = f"token_recovery_sent_{acc.name}"
    if context.user_data.get(key):
        return
    context.user_data[key] = True
    await send_token_recovery_flow(update, context, acc.name)


async def handle_token_recovery_callback(
    data: str, query, uid: int, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    if not data.startswith("connect:recover:"):
        return False
    name = data.split(":", 2)[2].strip().lower()
    if not name or not query or not query.message:
        return False
    from .auth import resolve_account

    acc = resolve_account(name, uid)
    if not acc:
        await query.answer("Hesap bulunamadı", show_alert=True)
        return True
    update = Update(update_id=query.id, callback_query=query)
    await send_token_recovery_flow(update, context, acc.name, uid=uid)
    try:
        await query.answer("Token'ı bu sohbete yapıştır")
    except Exception:
        pass
    return True


def patch_on_text_token_paste() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_token_paste_patched", False):
        return

    _orig = ta.on_text

    async def on_text_patched(update, context):
        if not update.message or not update.message.text:
            return await _orig(update, context)
        from .connect_intel import plan_token_connect
        from .token_recovery import extract_jwt_from_text

        jwt = extract_jwt_from_text(update.message.text.strip())
        if jwt:
            uid = ta._uid(update)
            pending_add = context.user_data.get("pending_add")
            pending_refresh = context.user_data.pop("pending_token_refresh", None)
            if not pending_refresh:
                from .session_token_pending import get_pending_token_account

                pending_refresh = get_pending_token_account(uid)
            from .telegram_helpers import _session_pending_connect

            pending_connect = _session_pending_connect(context, uid)
            default_acc = ta._default_account(context, uid)

            def _plan():
                return plan_token_connect(
                    jwt,
                    uid,
                    pending_add=pending_add,
                    pending_refresh=pending_refresh,
                    pending_connect=pending_connect and not pending_add,
                    default_account=default_acc,
                )

            plan = await asyncio.to_thread(_plan)
            if plan.action == "reject":
                await update.message.reply_text(plan.message, parse_mode="HTML")
                return
            if plan.action == "save":
                if plan.message:
                    await update.message.reply_text(plan.message, parse_mode="HTML")
                context.user_data.pop("pending_add", None)
                from .autofarm_notify import reset_recovery_cooldown
                from .session_token_pending import clear_pending_token_account

                clear_pending_token_account(uid)
                reset_recovery_cooldown(plan.account_name)
                await ta._save_account(
                    update, plan.account_name, jwt, uid=uid, context=context
                )
                return
        return await _orig(update, context)

    ta.on_text = on_text_patched
    ta._token_paste_patched = True


def patch_save_account_token_errors() -> None:
    """Token recovery — connect_save wired ise atla (recovery orada)."""
    from . import telegram_app as ta

    if getattr(ta, "_save_account_recovery_patched", False):
        return
    if getattr(ta, "_save_account_wired", False):
        ta._save_account_recovery_patched = True
        log.info("save_account recovery atlandı (connect_save wired)")
        return

    _orig = ta._save_account

    async def _save_account_patched(update, name, token, *, uid=None, context=None):
        try:
            return await _orig(update, name, token, uid=uid, context=context)
        except Exception as e:
            if is_token_auth_error(str(e)):
                msg = update.effective_message
                if msg:
                    await msg.reply_text(
                        "❌ Bu token da geçersiz.\n\n"
                        "Oyunda çıkış yap → tekrar giriş → F5 → konsol kodunu yeniden çalıştır.",
                        parse_mode="HTML",
                    )
                    if context is not None:
                        await send_token_recovery_flow(
                            update, context, name, uid=uid or ta._uid(update)
                        )
                return
            raise

    ta._save_account = _save_account_patched
    ta._save_account_recovery_patched = True


def patch_dashboard_token_recovery() -> None:
    from . import telegram_ui as ui
    from .dashboard_view import snap_is_live

    if getattr(ui, "_token_recovery_dash_patched", False):
        return

    _orig = ui.dashboard_inline_markup

    def dashboard_inline_markup_patched(acc, snap=None, *, user_accs=None):
        markup = _orig(acc, snap, user_accs=user_accs)
        row = snap or {}
        if snap_is_live(row):
            return markup
        if not is_token_auth_error(str(row.get("error") or "")):
            return markup
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    "🔑 Yeni token al",
                    callback_data=f"connect:recover:{acc.name.strip().lower()}",
                )
            ]
        ]
        rows.extend(list(markup.inline_keyboard))
        return InlineKeyboardMarkup(rows)

    ui.dashboard_inline_markup = dashboard_inline_markup_patched  # type: ignore[assignment]
    ui._token_recovery_dash_patched = True


def patch_dashboard_unavailable_message() -> None:
    from . import telegram_ui as ui
    from .dashboard_view import format_dashboard_unavailable, snap_is_live

    if getattr(ui, "_token_recovery_msg_patched", False):
        return

    _orig = ui.format_dashboard_html

    def format_dashboard_html_patched(acc, snap=None):
        row = snap
        if row is None:
            from .dynamic_context import snapshot_account

            row = snapshot_account(acc)
        if not snap_is_live(row) and is_token_auth_error(str(row.get("error") or "")):
            return (
                format_dashboard_unavailable(acc, row)
                + "\n\n<b>🔑 Ne yapmalısın?</b>\n"
                "Alttaki <b>«Yeni token al»</b> — konsol kodu gelir, token'ı burada beklerim."
            )
        return _orig(acc, snap)

    ui.format_dashboard_html = format_dashboard_html_patched  # type: ignore[assignment]
    ui._token_recovery_msg_patched = True


def patch_dashboard_flood_auto_recovery() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_token_recovery_flood_patched", False):
        return

    _orig = ta._open_dashboard_tracked

    async def _open_dashboard_tracked_with_recovery(update, context, acc, *, edit=False, force_refresh=False):
        from .dynamic_context import peek_snapshot_cache

        await _orig(update, context, acc, edit=edit, force_refresh=force_refresh)
        snap = peek_snapshot_cache(acc.name, allow_stale=True) or {}
        if not edit:
            await maybe_auto_token_recovery(update, context, acc, snap)

    ta._open_dashboard_tracked = _open_dashboard_tracked_with_recovery
    ta._token_recovery_flood_patched = True


def install_token_recovery_hooks() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from . import callbacks as cb

    patch_on_text_token_paste()
    patch_save_account_token_errors()
    patch_dashboard_token_recovery()
    patch_dashboard_unavailable_message()
    patch_dashboard_flood_auto_recovery()

    _orig = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if await handle_token_recovery_callback(data, query, uid, context):
            return
        return await _orig(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    from . import telegram_app as ta

    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched
    _INSTALLED = True
    log.info("Token recovery hook'ları kuruldu")
