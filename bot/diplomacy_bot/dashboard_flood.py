"""Dashboard flood önleme — tek mesaj, sessiz önbellek, yenile sadece istekle."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .dashboard_session import (
    clear_dashboard_pin,
    delete_pinned_dashboard,
    get_dashboard_pin,
    set_dashboard_pin,
)
from .dynamic_context import is_snapshot_fresh, peek_snapshot_cache
from .store import Account
from .ui_tracker import edit_safe, spawn_tracked, transition_text, tracker_footer

log = logging.getLogger(__name__)


def _snap_ok(snap: dict | None) -> bool:
    return bool(snap and "error" not in snap)


def install_dashboard_flood_patch() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_dashboard_flood_installed", False):
        return

    _orig = ta._open_dashboard_tracked
    ta._open_dashboard_tracked = _open_dashboard_tracked_patched  # type: ignore[assignment]
    ta._open_dashboard_tracked_orig = _orig
    ta._dashboard_flood_installed = True
    log.info("Dashboard tek-mesaj patch kuruldu")


async def _open_dashboard_tracked_patched(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    acc: Account,
    *,
    edit: bool = False,
    force_refresh: bool = False,
) -> None:
    from . import telegram_app as ta
    from .telegram_ui import dashboard_inline_markup, format_dashboard_html

    q = update.callback_query
    bot = update.get_bot()
    uid = ta._uid(update)
    user_accs = ta._user_accounts(uid)

    def _schedule_publish(chat_id: int, msg_id: int, *, force: bool) -> None:
        spawn_tracked(
            context.application,
            ta._publish_dashboard_message(
                bot, chat_id, msg_id, acc, force_refresh=force, uid=uid
            ),
            name="dash-refresh",
        )

    def _render(snap: dict, *, footer: str = "") -> tuple[str, InlineKeyboardMarkup]:
        text = format_dashboard_html(acc, snap)
        if footer:
            text = f"{text}{footer}"
        return text, dashboard_inline_markup(acc, snap, user_accs=user_accs)

    async def _edit_dashboard(target_chat: int, target_msg: int, *, footer: str = "") -> bool:
        cached = peek_snapshot_cache(acc.name, allow_stale=True)
        if _snap_ok(cached):
            text, markup = _render(cached, footer=footer)
            ok = await edit_safe(
                bot, target_chat, target_msg, text,
                reply_markup=markup, disable_web_page_preview=True,
            )
            if ok:
                set_dashboard_pin(uid, target_chat, target_msg)
                if force_refresh or not is_snapshot_fresh(acc.name):
                    _schedule_publish(target_chat, target_msg, force=force_refresh)
            return ok
        key = "dash:refresh" if force_refresh else "dash:home"
        body = transition_text(key) if not edit else transition_text("keyboard:dashboard")
        ok = await edit_safe(bot, target_chat, target_msg, body, reply_markup=None)
        if ok:
            set_dashboard_pin(uid, target_chat, target_msg)
            _schedule_publish(target_chat, target_msg, force=True)
        return ok

    async def _send_new_dashboard(msg) -> None:
        cached = peek_snapshot_cache(acc.name, allow_stale=True)
        if _snap_ok(cached) and not force_refresh:
            sent = await msg.reply_text(
                format_dashboard_html(acc, cached),
                parse_mode="HTML",
                reply_markup=dashboard_inline_markup(acc, cached, user_accs=user_accs),
                disable_web_page_preview=True,
            )
            set_dashboard_pin(uid, sent.chat_id, sent.message_id)
            if not is_snapshot_fresh(acc.name):
                _schedule_publish(sent.chat_id, sent.message_id, force=False)
            return
        sent = await msg.reply_text(transition_text("keyboard:dashboard"), parse_mode="HTML")
        set_dashboard_pin(uid, sent.chat_id, sent.message_id)
        stale = peek_snapshot_cache(acc.name, allow_stale=True)
        if _snap_ok(stale):
            await edit_safe(
                bot,
                sent.chat_id,
                sent.message_id,
                format_dashboard_html(acc, stale) + tracker_footer("Güncelleniyor"),
                reply_markup=dashboard_inline_markup(acc, stale, user_accs=user_accs),
                disable_web_page_preview=True,
            )
        _schedule_publish(sent.chat_id, sent.message_id, force=True)

    if edit and q and q.message:
        chat_id = q.message.chat_id
        msg_id = q.message.message_id
        footer = tracker_footer("Güncelleniyor") if force_refresh else ""
        if await _edit_dashboard(chat_id, msg_id, footer=footer):
            return
        clear_dashboard_pin(uid)
        await _send_new_dashboard(q.message)
        return

    msg = update.effective_message
    if not msg:
        return

    chat_id = msg.chat_id
    pin = get_dashboard_pin(uid)

    if pin and pin[0] == chat_id:
        footer = tracker_footer("Güncelleniyor") if force_refresh else ""
        if await _edit_dashboard(pin[0], pin[1], footer=footer):
            return
        clear_dashboard_pin(uid)
    elif pin:
        await delete_pinned_dashboard(bot, uid)

    await _send_new_dashboard(msg)
