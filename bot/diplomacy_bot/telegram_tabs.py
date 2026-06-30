"""Savaş ve Seyahat sekmeleri — callback handler."""

from __future__ import annotations

import asyncio
import html
import logging
from types import SimpleNamespace
from urllib.parse import unquote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .auth import resolve_account
from .keyboard_prefs import reply_keyboard_for_user, toggle_reply_keyboard
from .store import Account
from .tab_nav import format_travel_tab_html, tab_nav_row, travel_tab_markup, war_tab_markup
from .travel_commands import format_travel_status, run_travel
from .ui_tracker import edit_safe

log = logging.getLogger(__name__)


class _PinnedQuery:
    """Pinned dashboard mesajını sekme olarak düzenlemek için minimal query."""

    def __init__(self, bot, chat_id: int, message_id: int):
        self.message = SimpleNamespace(chat_id=chat_id, message_id=message_id)
        self._bot = bot

    def get_bot(self):
        return self._bot


async def open_tab_from_message(update: Update, acc: Account, tab: str) -> None:
    uid = update.effective_user.id if update.effective_user else 0
    from .dashboard_session import get_dashboard_pin

    pin = get_dashboard_pin(uid)
    bot = update.get_bot()
    if pin:
        q = _PinnedQuery(bot, pin[0], pin[1])
        if tab == "war":
            await open_war_tab(q, uid, acc.name)
        else:
            await open_travel_tab(q, uid, acc.name)
        return
    if tab == "war":
        await send_war_tab_message(update, acc)
    else:
        await send_travel_tab_message(update, acc)


def _travel_shortcuts(token: str, acc: Account) -> list[dict]:
    from .account_runtime import interactive_account_context
    from .game_api import get_profile
    from .modules.travel import list_provinces

    with interactive_account_context(acc):
        provinces = list_provinces(token)
        if not provinces:
            return []
        try:
            prof = get_profile(token)
            country = prof.country_name or ""
            current = (prof.province_name or "").strip().lower()
        except Exception:
            country = ""
            current = ""

        same: list[dict] = []
        other: list[dict] = []
        for p in provinces:
            name = (p.get("name") or "").strip()
            if not name or name.lower() == current:
                continue
            cn = (p.get("country_name") or "").strip()
            if country and cn == country:
                same.append(p)
            else:
                other.append(p)
        same.sort(key=lambda x: str(x.get("name") or ""))
        other.sort(key=lambda x: str(x.get("name") or ""))
        return (same + other)[:5]


async def _travel_tab_payload(acc: Account) -> tuple[str, InlineKeyboardMarkup]:
    from .account_runtime import interactive_account_context
    from .game_api import get_profile

    def _load():
        with interactive_account_context(acc):
            st = format_travel_status(acc.token)
            try:
                p = get_profile(acc.token).province_name
            except Exception:
                p = None
            shortcuts = _travel_shortcuts(acc.token, acc)
            return st, p, shortcuts

    status, prov, shortcuts = await asyncio.to_thread(_load)
    text = format_travel_tab_html(status, province=prov, has_shortcuts=bool(shortcuts))
    return text, travel_tab_markup(shortcuts)


async def _war_pack(acc: Account):
    from .account_runtime import interactive_account_context
    from .game_features import fetch_war_board

    def _load():
        with interactive_account_context(acc):
            return fetch_war_board(acc.token, acc.name)

    return await asyncio.to_thread(_load)


async def send_war_tab_message(update: Update, acc: Account) -> None:
    from .account_config import get_config
    from .war_board import format_war_board_html

    pack = await _war_pack(acc)
    msg = update.effective_message
    if not msg:
        return
    if not pack.get("ok"):
        await msg.reply_text(
            f"❌ {pack.get('error', 'Savaş listesi alınamadı')}",
            reply_markup=InlineKeyboardMarkup([tab_nav_row(active="war")]),
        )
        return
    analysis = pack.get("analysis") or {}
    await msg.reply_text(
        format_war_board_html(pack.get("data") or {}, analysis, get_config(acc.name)),
        parse_mode="HTML",
        reply_markup=war_tab_markup(analysis, acc.name),
        disable_web_page_preview=True,
    )


async def send_travel_tab_message(update: Update, acc: Account) -> None:
    text, markup = await _travel_tab_payload(acc)
    msg = update.effective_message
    if not msg:
        return
    await msg.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def open_war_tab(query, uid: int, default_account: str | None) -> None:
    from .account_config import get_config
    from .war_board import format_war_board_html

    acc = resolve_account(default_account, uid) if default_account else None
    if not acc or not query or not query.message:
        return
    pack = await _war_pack(acc)
    if not pack.get("ok"):
        text = f"❌ {html.escape(str(pack.get('error') or 'Savaş listesi alınamadı'))}"
        markup = InlineKeyboardMarkup(
            [tab_nav_row(active="war"), [InlineKeyboardButton("🔄 Tekrar", callback_data="menu:war")]]
        )
    else:
        analysis = pack.get("analysis") or {}
        text = format_war_board_html(pack.get("data") or {}, analysis, get_config(acc.name))
        markup = war_tab_markup(analysis, acc.name)
    await edit_safe(
        query.get_bot(), query.message.chat_id, query.message.message_id, text,
        parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True,
    )


async def open_travel_tab(query, uid: int, default_account: str | None) -> None:
    acc = resolve_account(default_account, uid) if default_account else None
    if not acc or not query or not query.message:
        return
    text, markup = await _travel_tab_payload(acc)
    await edit_safe(
        query.get_bot(), query.message.chat_id, query.message.message_id, text,
        parse_mode="HTML", reply_markup=markup,
    )


async def handle_travel_action(data: str, query, uid: int, default: str | None) -> bool:
    if not data.startswith("travel:"):
        return False
    acc = resolve_account(default, uid) if default else None
    if not acc or not query:
        return False
    from .account_runtime import interactive_account_context

    op = data.split(":", 1)[1]
    if op == "refresh":
        try:
            await query.answer("Yenileniyor…")
        except Exception:
            pass
        await open_travel_tab(query, uid, default)
        return True

    if op.startswith("go:"):
        dest = unquote(op[3:], errors="replace").strip()
        if not dest:
            try:
                await query.answer("Hedef seçilemedi", show_alert=True)
            except Exception:
                pass
            return True

        def _run():
            with interactive_account_context(acc):
                return run_travel(acc.token, dest)

        r = await asyncio.to_thread(_run)
        msg = "✅ Seyahat başladı." if r.get("ok") else f"❌ {r.get('error', 'seyahat olmadı')}"
        try:
            await query.answer(msg[:180], show_alert=not r.get("ok"))
        except Exception:
            pass
        await open_travel_tab(query, uid, default)
        return True

    if op == "cancel":

        def _run():
            with interactive_account_context(acc):
                return run_travel(acc.token, "iptal")

        r = await asyncio.to_thread(_run)
        msg = "✅ Seyahat iptal edildi." if r.get("ok") else f"❌ {r.get('error', 'iptal olmadı')}"
        try:
            await query.answer(msg[:180], show_alert=not r.get("ok"))
        except Exception:
            pass
        await open_travel_tab(query, uid, default)
        return True

    return False


async def handle_tab_menu_callback(
    data: str, query, uid: int, default: str | None, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    if data == "menu:war":
        await open_war_tab(query, uid, default)
        return True
    if data == "menu:travel":
        await open_travel_tab(query, uid, default)
        return True
    if data == "cfg:keyboard:toggle":
        on = toggle_reply_keyboard(uid)
        try:
            await query.answer("Alttaki butonlar açıldı" if on else "Alttaki butonlar kapatıldı")
        except Exception:
            pass
        kb = reply_keyboard_for_user(uid)
        if query.message and kb is not None:
            note = (
                "⌨️ <b>Alttaki butonlar açıldı.</b>" if on
                else "⌨️ <b>Alttaki butonlar kapatıldı.</b> — sadece sekmeleri kullan."
            )
            await query.message.reply_text(note, parse_mode="HTML", reply_markup=kb)
        from .telegram_helpers import _send_settings

        acc = resolve_account(default, uid) if default else None
        if acc:
            await _send_settings(query, acc, edit=False, uid=uid)
        return True
    if await handle_travel_action(data, query, uid, default):
        return True
    return False


def install_tab_hooks() -> None:
    from . import callbacks as cb
    from . import telegram_app as ta

    if getattr(ta, "_tab_hooks_installed", False):
        return
    _orig = cb.handle_callback

    async def patched(update, context, data, default, query, uid):
        if await handle_tab_menu_callback(data, query, uid, default, context):
            return
        return await _orig(update, context, data, default, query, uid)

    cb.handle_callback = patched
    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = patched
    ta._tab_hooks_installed = True
    log.info("Savaş/Seyahat sekme hook kuruldu")
