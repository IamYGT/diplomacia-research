"""Telegram UI/account/tracked-action helper'ları — telegram_app'ten ayrıldı.

Sadece dış modüllerden import eder; telegram_app/callbacks'e BAĞLI DEĞİL (acyclic).
Bu dosyadaki her helper pure veya dış-bağımlı (auth, store, ui_tracker, telegram_ui).
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .auth import bot_allows_user, default_account_name, is_admin, resolve_account, scoped_list_accounts
from .store import Account, get_session, upsert_session
from .telegram_ui import (
    accounts_inline_markup,
    fleet_inline_markup,
    format_accounts_html,
    format_fleet_html,
    format_settings_html,
    result_with_home_markup,
    settings_inline_markup,
)
from .ui_tracker import edit_safe, tracker_footer, transition_text

log = logging.getLogger(__name__)

USER_FACING_ERROR = "İşlem başarısız. /start ile yeniden dene."


def _callback_toast(data: str) -> str:
    exact = {
        "dash:refresh": "🔄 Güncelleniyor…",
        "dash:home": "🏠 Ana sayfa…",
        "menu:settings": "⚙️ Ayarlar…",
        "menu:accounts": "👤 Hesaplar…",
        "menu:fleet": "👥 Filo…",
        "toggle:autofarm": "🤖 Autofarm…",
    }
    if data in exact:
        return exact[data]
    if data == "action:farmboard":
        return "🌾 Farm merkezi…"
    if data in ("action:farm", "action:smartfarm"):
        return "🌾 Farm çalışıyor…"
    if data == "action:hap":
        return "💊 Can dolduruluyor…"
    if data == "action:stat":
        return "⚡ Stat merkezi…"
    if data == "action:statboard":
        return "⚡ Stat merkezi…"
    if data == "action:daily":
        return "🎁 Günlük alınıyor…"
    if data == "action:plan":
        return "📋 Plan…"
    if data == "action:questlist":
        return "📋 Görevler…"
    if data == "action:wars":
        return "⚔️ Savaş…"
    if data == "action:warcontrib":
        return "⚔️ Katkı…"
    if data == "action:training":
        return "🏋️ Antrenman…"
    if data == "action:military":
        return "🪖 Asker…"
    if data == "action:myfactory":
        return "🏭 Fabrika…"
    if data == "action:craft":
        return "💎 Hap üret…"
    if data == "action:countries":
        return "🌍 Ülkeler…"
    if data == "action:online":
        return "🌐 Online…"
    if data == "action:autostatus":
        return "🤖 Otomasyon…"
    if data == "action:passive":
        return "⚡ Pasif stat…"
    if data == "action:ping":
        return "📡 Ping…"
    if data == "menu:extras":
        return "⋯ Ek menü…"
    if data.startswith("fleet:tick:"):
        return "👥 Filo tick…"
    if data.startswith("cfg:"):
        return "⚙️ Kaydediliyor…"
    if data.startswith("role:set:"):
        return "✅ Rol güncelleniyor…"
    if data.startswith("nav:account:"):
        return "👤 Hesap değişiyor…"
    return "⏳ İşleniyor…"


def _menu_status_text(action: str) -> str:
    key = action.strip().lower()
    menu_map = {
        "farm yap": "🌾 Farm çalışıyor…",
        "akıllı farm": "🌾 Akıllı farm…",
        "hap kullan": "💊 Can dolduruluyor…",
        "stat harca": "⚡ Stat harcanıyor…",
        "günlük": "🎁 Günlük alınıyor…",
        "planım": "📋 Plan hazırlanıyor…",
        "ne durumdayım": "📊 Durum alınıyor…",
    }
    return menu_map.get(key, "⏳ İşleniyor…")


async def _loading_edit(query, text: str = "⏳ İşleniyor…") -> None:
    """Anında geri bildirim — arka plan işlemi sürerken mesaj güncellenir."""
    if query and query.message:
        body = f"{text}{tracker_footer('İşlem sürüyor')}"
        await edit_safe(
            query.get_bot(),
            query.message.chat_id,
            query.message.message_id,
            body,
        )


async def _begin_tracked_action(query, transition_key: str) -> tuple | None:
    if not query or not query.message:
        return None
    bot = query.get_bot()
    chat_id = query.message.chat_id
    msg_id = query.message.message_id
    await edit_safe(bot, chat_id, msg_id, transition_text(transition_key), reply_markup=None)
    return bot, chat_id, msg_id


async def _finish_tracked_action(
    bot,
    chat_id: int,
    msg_id: int,
    text: str,
    *,
    parse_mode: str | None = "Markdown",
) -> None:
    await edit_safe(
        bot,
        chat_id,
        msg_id,
        text,
        reply_markup=result_with_home_markup(),
        parse_mode=parse_mode,
    )


async def _open_keyboard_screen(
    update: Update,
    transition_key: str,
    text: str,
    markup: InlineKeyboardMarkup | None,
) -> None:
    """Klavye menüsü — önce geçiş metni, sonra tek edit ile içerik."""
    msg = update.effective_message
    if not msg:
        return
    bot = update.get_bot()
    sent = await msg.reply_text(transition_text(transition_key), parse_mode="HTML")
    await edit_safe(bot, sent.chat_id, sent.message_id, text, reply_markup=markup)


def _uid(update: Update) -> int:
    return update.effective_user.id if update.effective_user else 0


def admin_only(func: Callable):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = _uid(update)
        if not is_admin(uid):
            await update.message.reply_text(
                f"⛔ Yalnızca yönetici.\nTelegram ID: `{uid}`",
                parse_mode="Markdown",
            )
            return
        return await func(update, context)

    return wrapper


def user_required(func: Callable):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = _uid(update)
        if not bot_allows_user(uid):
            await update.message.reply_text("⛔ Bot şu an kapalı modda.")
            return
        return await func(update, context)

    return wrapper


def _user_accounts(uid: int) -> list[Account]:
    return scoped_list_accounts(uid)


def _resolve_accounts(arg: str | None, uid: int) -> list[Account]:
    if not arg or arg.lower() == "all":
        return _user_accounts(uid)
    acc = resolve_account(arg, uid)
    return [acc] if acc else []


def _default_account(context: ContextTypes.DEFAULT_TYPE, uid: int) -> str | None:
    """Varsayılan hesap — bellek, SQLite oturum, ilk hesap sırası."""
    stored = (context.user_data.get("default_account") or "").strip().lower()
    if stored and resolve_account(stored, uid):
        return stored
    if stored:
        context.user_data.pop("default_account", None)
    sess = get_session(uid)
    if sess and sess.get("active_account"):
        db_name = str(sess["active_account"]).strip().lower()
        if db_name and resolve_account(db_name, uid):
            context.user_data["default_account"] = db_name
            return db_name
    accs = _user_accounts(uid)
    if accs:
        name = accs[0].name
        context.user_data["default_account"] = name
        upsert_session(uid, active_account=name)
        return name
    return None


def _set_default_account(context: ContextTypes.DEFAULT_TYPE, uid: int, name: str) -> None:
    name = name.strip().lower()
    context.user_data["default_account"] = name
    upsert_session(uid, active_account=name)


def _session_pending_connect(context: ContextTypes.DEFAULT_TYPE, uid: int) -> bool:
    if context.user_data.get("pending_connect"):
        return True
    sess = get_session(uid)
    return bool(sess and int(sess.get("pending_connect") or 0))


def _set_pending_connect(context: ContextTypes.DEFAULT_TYPE, uid: int, pending: bool) -> None:
    if pending:
        context.user_data["pending_connect"] = True
    else:
        context.user_data.pop("pending_connect", None)
    upsert_session(uid, pending_connect=pending)


def _chunk(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _inline_markup(buttons: list[list[tuple[str, str]]] | None) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in buttons]
    )


async def _reply_long(
    update: Update,
    text: str,
    parse_mode: str | None = "Markdown",
    *,
    inline_buttons: list[list[tuple[str, str]]] | None = None,
):
    markup = _inline_markup(inline_buttons)
    for i, part in enumerate(_chunk(text)):
        kw = {"parse_mode": parse_mode}
        if i == 0 and markup:
            kw["reply_markup"] = markup
        try:
            await update.message.reply_text(part, **kw)
        except Exception:
            await update.message.reply_text(part, reply_markup=kw.get("reply_markup"))


def _active_account(context: ContextTypes.DEFAULT_TYPE, uid: int) -> Account | None:
    name = _default_account(context, uid)
    if not name:
        return None
    return resolve_account(name, uid)


async def _send_settings(update: Update, acc: Account, *, edit: bool = False, uid: int | None = None):
    snap = {"username": acc.username or acc.name}
    user_accs = _user_accounts(uid) if uid else None
    text = format_settings_html(acc, snap)
    markup = settings_inline_markup(acc, user_accs=user_accs)
    q = update.callback_query
    if edit and q and q.message:
        await edit_safe(
            q.get_bot(),
            q.message.chat_id,
            q.message.message_id,
            text,
            reply_markup=markup,
        )
        return
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def _send_accounts_picker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    edit: bool = False,
    page: int = 0,
):
    uid = _uid(update)
    default = _default_account(context, uid) or "?"
    accs = _user_accounts(uid)
    text = format_accounts_html(default, accs)
    markup = accounts_inline_markup(default, accs, page=page)
    q = update.callback_query
    if edit and q and q.message:
        await edit_safe(
            q.get_bot(),
            q.message.chat_id,
            q.message.message_id,
            text,
            reply_markup=markup,
        )
        return
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def _reply_action_result(update: Update, text: str, *, parse_mode: str | None = "Markdown"):
    """Aksiyon sonrası ana sayfaya dön butonu — parse hatasında düz metin."""
    msg = update.effective_message
    q = update.callback_query
    markup = result_with_home_markup()
    body = text
    mode = parse_mode
    if q and q.message:
        try:
            await q.edit_message_text(body, parse_mode=mode, reply_markup=markup)
            return
        except Exception:
            try:
                await q.edit_message_text(body, reply_markup=markup)
                return
            except Exception:
                pass
    if msg:
        try:
            await msg.reply_text(body, parse_mode=mode, reply_markup=markup)
        except Exception:
            await msg.reply_text(body, reply_markup=markup)


async def _send_fleet(update: Update, context: ContextTypes.DEFAULT_TYPE, *, edit: bool = False):
    uid = _uid(update)
    default = _default_account(context, uid) or "?"
    accs = _user_accounts(uid)
    text = format_fleet_html(default, accs)
    markup = fleet_inline_markup(default, accs)
    q = update.callback_query
    if edit and q and q.message:
        await edit_safe(
            q.get_bot(),
            q.message.chat_id,
            q.message.message_id,
            text,
            reply_markup=markup,
        )
        return
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def _try_extra_feature_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
    acc: Account,
    query,
) -> bool:
    from .feature_handlers import try_extra_feature_action

    return await try_extra_feature_action(
        update,
        context,
        data,
        acc,
        query,
        begin_tracked_action=_begin_tracked_action,
        finish_tracked_action=_finish_tracked_action,
    )
