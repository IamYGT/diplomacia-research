from __future__ import annotations

import asyncio
import html
import json
import logging
from functools import wraps
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import Conflict
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from . import ai_agent, farmer, game_api
from .telegram_ui import (
    accounts_inline_markup,
    dashboard_inline_markup,
    fleet_inline_markup,
    format_accounts_html,
    format_dashboard_html,
    format_extras_html,
    format_fleet_html,
    connect_inline_markup,
    format_help_html,
    format_token_guide_html,
    format_no_ai_fallback_html,
    format_settings_html,
    format_welcome_html,
    extras_inline_markup,
    main_reply_keyboard,
    no_ai_fallback_markup,
    normalize_menu_text,
    result_with_home_markup,
    role_label,
    role_picker_markup,
    settings_inline_markup,
    setup_bot_ui,
    back_home_button,
)
from .account_config import AccountConfig, BOT_ROLES, get_config, normalize_role, update_config_field
from .fleet_manager import format_fleet_summary, tick_fleet
from .account_pool import format_pool_status, get_proxy_by_id, load_intel_summary, load_rules, suggest_proxy
from .account_runtime import account_context, interactive_account_context, interactive_run, run_for_account
from .dynamic_context import invalidate_snapshot_cache, is_snapshot_fresh, peek_snapshot_cache
from .catalog import search_endpoints
from .auth import (
    bot_allows_user,
    can_access_account,
    default_account_name,
    is_admin,
    resolve_account,
    scoped_list_accounts,
)
from .config import (
    AUTOFARM_INTERVAL_SEC,
    GEMINI_API_KEY,
    MAX_ACCOUNTS_PER_USER,
    TELEGRAM_ADMIN_IDS,
    TELEGRAM_BOT_TOKEN,
)
from .stealth_client import cooldown_remaining_sec
from .store import (
    Account,
    add_account,
    autofarm_due,
    bootstrap_legacy,
    clear_session_pending,
    count_accounts_for_user,
    get_account,
    get_account_for_user,
    get_session,
    init_db,
    list_accounts,
    log_action,
    proxy_assignments,
    remove_account,
    set_autofarm,
    set_proxy,
    update_after_farm,
    upsert_session,
)

from .user_errors import (
    format_craft_preflight,
    format_daily_preflight,
    format_farm_preflight,
    format_hap_preflight,
    format_pill_error,
    format_quest_claim_preflight,
    format_stat_preflight,
    format_training_preflight,
    format_war_contrib_preflight,
)
from .ui_tracker import edit_safe, spawn_tracked, tracker_footer, transition_text
from .crash_notify import send_crash_notify, summarize_update
from .token_console import format_console_script_telegram
from .version import get_version_label
from .telegram_helpers import (
    USER_FACING_ERROR,
    _active_account,
    _begin_tracked_action,
    _callback_toast,
    _chunk,
    _default_account,
    _finish_tracked_action,
    _inline_markup,
    _loading_edit,
    _menu_status_text,
    _open_keyboard_screen,
    _reply_action_result,
    _reply_long,
    _resolve_accounts,
    _send_accounts_picker,
    _send_fleet,
    _send_settings,
    _session_pending_connect,
    _set_default_account,
    _set_pending_connect,
    _try_extra_feature_action,
    _uid,
    _user_accounts,
    admin_only,
    user_required,
)

log = logging.getLogger(__name__)


HELP_TEXT = f"""
🎮 *Diplomacy YGT Bot {get_version_label()}* — modüler AI + tam API

*🧠 Yapay zeka (dinamik)*
Serbest mesaj → canlı durumuna göre koç / aksiyon
`akıllı farm` — stat + training + work tek döngü
`planım` | `stat harca` | `fabrika ayarla foreign`
Koç: `can ne işe yarıyor` | `fabrika stratejisi`
/play /ai — Gemini plan
/confirm /cancel

*🔌 Ham API*
/api GET /quests [hesap]
/setaccount isim

*Hesap*
/accounts /add /remove /whoami /version

*Farm*
/farm [n] [hesap]
/autofarm on|off
/setfabric isim uuid|own|foreign|auto
/plan [hesap]
/daily /ping /status /report

*Multi-IP*
/proxies /setproxy /intel /cooldown
""".strip()


async def _dispatch_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Klavye butonları — AI'ya gitmeden doğrudan işlem."""
    uid = _uid(update)
    action = action.strip().lower()
    acc = _active_account(context, uid)

    if action == "dashboard":
        if not acc:
            await update.message.reply_text(
                "Henüz hesap yok. /connect ile bağla.",
                reply_markup=connect_inline_markup(),
            )
            return
        await _send_dashboard(update, acc, context)
        return

    if action == "ayarlar":
        if not acc:
            await update.message.reply_text("Henüz hesap yok. /connect", reply_markup=connect_inline_markup())
            return
        text = format_settings_html(acc, {"username": acc.username or acc.name})
        await _open_keyboard_screen(
            update,
            "keyboard:ayarlar",
            text,
            settings_inline_markup(acc),
        )
        return

    if action == "yardım":
        await update.message.reply_text(
            format_help_html(),
            parse_mode="HTML",
            reply_markup=main_reply_keyboard(),
        )
        return

    if action == "tüm hesaplar":
        default = _default_account(context, uid) or "?"
        user_accs = _user_accounts(uid)
        await _open_keyboard_screen(
            update,
            "keyboard:accounts",
            format_accounts_html(default, user_accs),
            accounts_inline_markup(default, user_accs),
        )
        return

    if action == "filo":
        default = _default_account(context, uid) or "?"
        user_accs = _user_accounts(uid)
        await _open_keyboard_screen(
            update,
            "keyboard:filo",
            format_fleet_html(default, user_accs),
            fleet_inline_markup(default, user_accs),
        )
        return

    if not acc:
        await update.message.reply_text("Aktif hesap yok. /connect", reply_markup=connect_inline_markup())
        return

    quick_actions = {
        "farm yap",
        "akıllı farm",
        "hap kullan",
        "stat harca",
        "günlük",
        "planım",
        "ne durumdayım",
    }
    if action in quick_actions:
        status = await update.message.reply_text(_menu_status_text(action))
        from . import intent_router

        def _fast():
            with interactive_account_context(acc):
                return intent_router.try_fast_path(action, acc.name)

        fast = await asyncio.to_thread(_fast)
        try:
            await status.delete()
        except Exception:
            pass
        if fast is not None:
            if fast.needs_confirmation and fast.pending_actions:
                context.user_data["pending_actions"] = fast.pending_actions
            await _reply_long(
                update,
                fast.reply,
                parse_mode=getattr(fast, "parse_mode", "Markdown"),
                inline_buttons=fast.inline_buttons,
            )
        else:
            await update.message.reply_text(f"❌ {USER_FACING_ERROR}")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await _run_ai(update, context, action)


async def cmd_fleet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_fleet(update, context)


@user_required
async def cmd_setrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if len(context.args) < 2:
        await update.message.reply_text(
            "Kullanım: /setrole <hesap> <farm|war|hybrid|hub|off>"
        )
        return
    name = context.args[0].lower()
    role = context.args[1].lower()
    if not resolve_account(name, uid):
        await update.message.reply_text("Hesap bulunamadı veya senin değil.")
        return
    if role not in BOT_ROLES:
        await update.message.reply_text(f"Geçersiz rol. Seçenekler: {', '.join(BOT_ROLES)}")
        return
    cfg = update_config_field(name, role=role)
    await update.message.reply_text(
        f"✅ *{name}* → {role_label(cfg.role)}",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )


async def _publish_dashboard_message(
    bot,
    chat_id: int,
    message_id: int,
    acc: Account,
    *,
    force_refresh: bool = False,
    uid: int = 0,
) -> None:
    from .dynamic_context import peek_snapshot_cache, snapshot_account
    from .stealth_client import cooldown_remaining_sec

    user_accs = _user_accounts(uid) if uid else None
    stale = peek_snapshot_cache(acc.name, allow_stale=True)

    def _render(snap: dict, *, footer: str = "") -> tuple[str, InlineKeyboardMarkup]:
        text = format_dashboard_html(acc, snap)
        if footer:
            text = f"{text}{footer}"
        markup = dashboard_inline_markup(acc, snap, user_accs=user_accs)
        return text, markup

    cached = peek_snapshot_cache(acc.name, allow_stale=force_refresh)
    if cached and "error" not in cached and not force_refresh:
        text, markup = _render(cached)
        await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)
        return

    if cached and "error" not in cached and force_refresh:
        text, markup = _render(cached, footer=tracker_footer("Güncelleniyor"))
        await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)

    cd = cooldown_remaining_sec()
    if cd > 0 and stale and "error" not in stale:
        text, markup = _render(
            stale,
            footer=f"\n\n<i>⏳ API bekleme ({cd} sn) — önbellek gösteriliyor</i>",
        )
        await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)
        return

    def _snap():
        with interactive_account_context(acc):
            return snapshot_account(acc, force_refresh=True)

    try:
        snap = await asyncio.wait_for(asyncio.to_thread(_snap), timeout=35.0)
    except asyncio.TimeoutError:
        snap = stale or {"error": "API zaman aşımı"}
    except Exception as e:
        log.exception("dashboard snapshot: %s", e)
        snap = stale or {"error": str(e)[:120]}

    if snap.get("error") and stale and "error" not in stale:
        text, markup = _render(
            stale,
            footer=f"\n\n<i>⚠️ Canlı veri alınamadı: {html.escape(str(snap['error'])[:80])}</i>",
        )
    else:
        text, markup = _render(snap)
    await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)


async def _open_dashboard_tracked(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    acc: Account,
    *,
    edit: bool = False,
    force_refresh: bool = False,
) -> None:
    """Önbellek anında; taze veri arka planda (Tor NEWNYM yok — okuma hızlı)."""
    q = update.callback_query
    bot = update.get_bot()
    uid = _uid(update)
    user_accs = _user_accounts(uid)

    def _spawn_refresh(chat_id: int, msg_id: int) -> None:
        spawn_tracked(
            context.application,
            _publish_dashboard_message(
                bot, chat_id, msg_id, acc, force_refresh=not is_snapshot_fresh(acc.name), uid=uid
            ),
            name="dash-refresh",
        )

    if edit and q and q.message:
        chat_id = q.message.chat_id
        msg_id = q.message.message_id
        if not force_refresh:
            cached = peek_snapshot_cache(acc.name, allow_stale=True)
            if cached and "error" not in cached:
                text = format_dashboard_html(acc, cached)
                markup = dashboard_inline_markup(acc, cached, user_accs=user_accs)
                await edit_safe(bot, chat_id, msg_id, text, reply_markup=markup, disable_web_page_preview=True)
                if not is_snapshot_fresh(acc.name):
                    _spawn_refresh(chat_id, msg_id)
                return
        cached = peek_snapshot_cache(acc.name, allow_stale=True)
        if cached and force_refresh:
            text = format_dashboard_html(acc, cached) + tracker_footer("Güncelleniyor")
            markup = dashboard_inline_markup(acc, cached, user_accs=user_accs)
            await edit_safe(bot, chat_id, msg_id, text, reply_markup=markup, disable_web_page_preview=True)
        elif cached and "error" not in cached:
            text = format_dashboard_html(acc, cached) + tracker_footer("Güncelleniyor")
            markup = dashboard_inline_markup(acc, cached, user_accs=user_accs)
            await edit_safe(bot, chat_id, msg_id, text, reply_markup=markup, disable_web_page_preview=True)
        elif not cached:
            key = "dash:refresh" if force_refresh else "dash:home"
            await edit_safe(bot, chat_id, msg_id, transition_text(key), reply_markup=None)
        _spawn_refresh(chat_id, msg_id)
        return

    msg = update.effective_message
    if msg:
        if not force_refresh:
            cached = peek_snapshot_cache(acc.name, allow_stale=True)
            if cached and "error" not in cached:
                sent = await msg.reply_text(
                    format_dashboard_html(acc, cached),
                    parse_mode="HTML",
                    reply_markup=dashboard_inline_markup(acc, cached, user_accs=user_accs),
                    disable_web_page_preview=True,
                )
                if not is_snapshot_fresh(acc.name):
                    _spawn_refresh(sent.chat_id, sent.message_id)
                return
        sent = await msg.reply_text(transition_text("keyboard:dashboard"), parse_mode="HTML")
        stale = peek_snapshot_cache(acc.name, allow_stale=True)
        if stale and "error" not in stale:
            await edit_safe(
                bot,
                sent.chat_id,
                sent.message_id,
                format_dashboard_html(acc, stale) + tracker_footer("Güncelleniyor"),
                reply_markup=dashboard_inline_markup(acc, stale, user_accs=user_accs),
                disable_web_page_preview=True,
            )
        spawn_tracked(
            context.application,
            _publish_dashboard_message(
                bot,
                sent.chat_id,
                sent.message_id,
                acc,
                force_refresh=True,
                uid=uid,
            ),
            name="kb-dashboard",
        )


async def _send_dashboard(
    update: Update,
    acc: Account,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    edit: bool = False,
    force_refresh: bool = False,
):
    await _open_dashboard_tracked(update, context, acc, edit=edit, force_refresh=force_refresh)


async def _send_connect_package(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    intro: str = "",
) -> None:
    """Rehber + kopyalanabilir konsol kodu."""
    msg = update.effective_message
    if not msg:
        return
    _set_pending_connect(context, _uid(update), True)
    await msg.reply_text(
        intro + format_token_guide_html(),
        parse_mode="HTML",
        reply_markup=connect_inline_markup(),
        disable_web_page_preview=True,
    )
    await msg.reply_text(format_console_script_telegram())


@user_required
async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    accs = _user_accounts(uid)
    intro = (
        "✅ Zaten bağlısın — yeni token gönderirsen hesap güncellenir.\n\n"
        if accs
        else ""
    )
    await _send_connect_package(update, context, intro=intro)


@user_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    default = _default_account(context, uid)
    acc = resolve_account(default, uid) if default else None
    linked = acc is not None
    await update.message.reply_text(
        format_welcome_html(uid, default, gemini_ok=bool(GEMINI_API_KEY), linked=linked),
        parse_mode="HTML",
        reply_markup=main_reply_keyboard() if linked else connect_inline_markup(),
    )
    if acc:
        await _send_dashboard(update, acc, context)
    elif not linked:
        _set_pending_connect(context, uid, True)


@user_required
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_dashboard(update, context)


@user_required
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    acc = _active_account(context, uid)
    if not acc:
        await update.message.reply_text("Hesap yok. /connect", reply_markup=connect_inline_markup())
        return
    await _send_settings(update, acc, uid=uid)


@user_required
async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    name = context.args[0].lower() if context.args else _default_account(context, uid)
    acc = resolve_account(name, uid) if name else None
    if not acc:
        accs = _user_accounts(uid)
        hint = f"\nSenin hesapların: {', '.join(a.name for a in accs)}" if accs else ""
        await update.message.reply_text(
            f"Hesap bulunamadı: `{name or '?'}`{hint}\n/connect ile hesap bağla",
            parse_mode="Markdown",
            reply_markup=connect_inline_markup() if not accs else None,
        )
        return
    await _send_dashboard(update, acc, context)


@user_required
async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 Diplomacy YGT Bot *{get_version_label()}*\n"
        f"Modüller: economy, factory, stats, training, war, orchestrator\n"
        f"Changelog: `bot/CHANGELOG.md`",
        parse_mode="Markdown",
    )


@user_required
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_help_html(),
        parse_mode="HTML",
        reply_markup=main_reply_keyboard(),
    )


@user_required
async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    await update.message.reply_text(f"Telegram user ID: `{uid}`", parse_mode="Markdown")


@user_required
async def cmd_setaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await update.message.reply_text(f"Varsayılan: `{_default_account(context, uid) or '—'}`", parse_mode="Markdown")
        return
    name = context.args[0].lower()
    if not resolve_account(name, uid):
        await update.message.reply_text("Hesap bulunamadı veya senin değil.")
        return
    _set_default_account(context, uid, name)
    await update.message.reply_text(f"✅ Varsayılan hesap: *{name}*", parse_mode="Markdown")


def _proxy_ctx(acc: Account):
    return account_context(acc)


async def _profile_for_account(a: Account):
    def _fetch():
        with account_context(a):
            return game_api.get_profile(a.token)

    return await asyncio.to_thread(_fetch)


async def _api_for_account(a: Account, fn):
    return await asyncio.to_thread(run_for_account, a, fn, a.token)


@user_required
async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not _user_accounts(uid):
        await update.message.reply_text(
            "Henüz hesap yok. Bağlamak için /connect",
            reply_markup=connect_inline_markup(),
        )
        return
    await _send_accounts_picker(update, context)


@user_required
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await update.message.reply_text(
            "Kullanım:\n"
            "• <code>/connect</code> — ilk hesap\n"
            "• <code>/add takma_ad</code> — ek hesap, sonra JWT yapıştır",
            parse_mode="HTML",
        )
        return
    alias = context.args[0].lower()
    name = default_account_name(uid, alias)
    token = " ".join(context.args[1:]).strip()
    if not token:
        context.user_data["pending_add"] = name
        await update.message.reply_text(
            f"<b>{html.escape(alias)}</b> için JWT yapıştır (<code>eyJ…</code>).",
            parse_mode="HTML",
        )
        return
    await _save_account(update, name, token, uid=uid, context=context)


async def _save_account(
    update: Update,
    name: str,
    token: str,
    *,
    uid: int | None = None,
    context: ContextTypes.DEFAULT_TYPE | None = None,
):
    uid = uid or _uid(update)
    msg = update.effective_message
    if not msg:
        return
    try:
        existing = resolve_account(name, uid)
        if count_accounts_for_user(uid) >= MAX_ACCOUNTS_PER_USER and not existing:
            await msg.reply_text(f"❌ En fazla {MAX_ACCOUNTS_PER_USER} hesap ekleyebilirsin.")
            return
        slot = suggest_proxy(proxy_assignments())

        def _fetch():
            with account_context(proxy_id=slot.id, proxy_url=slot.url or None):
                return game_api.get_profile(token)

        prof = await asyncio.to_thread(_fetch)
        acc = add_account(
            name,
            token,
            prof.player_id,
            prof.username,
            slot.id,
            slot.url,
            telegram_user_id=uid,
        )
        if context is not None:
            _set_default_account(context, uid, acc.name)
            _set_pending_connect(context, uid, False)
            context.user_data.pop("pending_add", None)
        log_action(
            "connect",
            account_name=acc.name,
            telegram_user_id=uid,
            result=f"{prof.username} lv{prof.level}",
        )
        await msg.reply_text(
            f"✅ <b>{acc.name}</b> bağlandı — {prof.username}\n"
            f"💰 {prof.balance:,} | lv{prof.level}\n\n"
            "🏠 Ana Sayfa ile panele geç.",
            parse_mode="HTML",
            reply_markup=main_reply_keyboard(),
        )
        if context is not None and acc:
            await _send_dashboard(update, acc, context)
    except Exception as e:
        log_action("connect", account_name=name, telegram_user_id=uid, result=str(e)[:200], success=False)
        await msg.reply_text(f"❌ {e}")


@user_required
async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await update.message.reply_text("/remove isim")
        return
    name = context.args[0].lower()
    if not resolve_account(name, uid):
        await update.message.reply_text("Hesap bulunamadı veya senin değil.")
        return
    if remove_account(name, telegram_user_id=uid):
        if context.user_data.get("default_account") == name:
            context.user_data.pop("default_account", None)
            upsert_session(uid, active_account="")
        log_action("remove", account_name=name, telegram_user_id=uid)
        await update.message.reply_text("✅ Hesap bottan kaldırıldı.")
    else:
        await update.message.reply_text("Silinemedi.")


@user_required
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    name = context.args[0].lower() if context.args and len(context.args) == 1 else _default_account(context, uid)
    acc = resolve_account(name, uid) if name else None
    if not acc:
        await update.message.reply_text("Hesap yok. /connect", reply_markup=connect_inline_markup())
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    await _send_dashboard(update, acc, context)


@user_required
async def cmd_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cycles, name_arg = 1, None
    if context.args:
        if context.args[0].isdigit():
            cycles = int(context.args[0])
            name_arg = context.args[1] if len(context.args) > 1 else None
        else:
            name_arg = context.args[0]
    uid = _uid(update)
    accs = _resolve_accounts(name_arg, uid)
    if not accs:
        await update.message.reply_text("Hesap yok. /connect", reply_markup=connect_inline_markup())
        return
    await update.message.reply_text(f"🌾 Farm ({cycles}x, {len(accs)} hesap, sıralı)...")
    results = []
    rules = load_rules()
    for i, a in enumerate(accs):
        if i > 0:
            await asyncio.sleep(rules.stagger_farm_sec)
        r = await asyncio.to_thread(
            farmer.run_farm, a.token, a.name, cycles, a.proxy_url or None, a.proxy_id or ""
        )
        update_after_farm(a.name, r.balance_after)
        results.append(farmer.format_farm_result(r))
    await update.message.reply_text("\n\n".join(results))


@user_required
async def cmd_setfabric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "/setfabric isim uuid\n"
            "/setfabric isim own — kendi eyalet fabrikası\n"
            "/setfabric isim foreign — bölgedeki en iyi yabancı fabrika\n"
            "/setfabric isim auto — eski otomatik (build dahil)"
        )
        return
    name, mode = context.args[0].lower(), context.args[1].lower()
    uid = _uid(update)
    if not resolve_account(name, uid):
        await update.message.reply_text("Hesap bulunamadı veya senin değil.")
        return
    if mode in ("own", "foreign", "auto"):
        update_config_field(name, work_mode=mode, preferred_factory_id=None)
        await update.message.reply_text(f"✅ {name} work_mode={mode}")
        return
    if len(mode) > 20:
        update_config_field(name, work_mode="fixed", preferred_factory_id=mode)
        await update.message.reply_text(f"✅ {name} → sabit fabrika `{mode}`", parse_mode="Markdown")
        return
    await update.message.reply_text("Geçersiz mod. own|foreign|auto veya fabrika UUID.")


@user_required
async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    accs = _resolve_accounts(context.args[0] if context.args else None, uid)
    if not accs:
        await update.message.reply_text("Hesap yok. /connect")
        return
    lines = []
    for a in accs:
        cfg = get_config(a.name)
        lines.append(
            f"*{a.name}* `{a.proxy_id}`\n"
            f"  mod: `{cfg.work_mode}` | hub: {'evet' if cfg.is_premium_hub else 'hayır'}\n"
            f"  fabrika: `{cfg.preferred_factory_id or '—'}` | build: {'evet' if cfg.allow_auto_build else 'hayır'}\n"
            f"  stat: {', '.join(cfg.stat_priority[:3])}… | training: {'on' if cfg.training_enabled else 'off'}\n"
            f"  savaş: {'on' if cfg.war_enabled else 'off'}"
        )
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


@user_required
async def cmd_setwar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hedef savaş seç: /setwar 2 veya /setwar uuid"""
    uid = _uid(update)
    if not context.args:
        await update.message.reply_text(
            "Kullanım:\n"
            "• <code>/setwar 2</code> — listedeki 2. savaş\n"
            "• <code>/setwar uuid</code> — doğrudan ID\n"
            "Önce <code>savaş</code> veya ⚔️ Savaş ile listeyi aç.",
            parse_mode="HTML",
        )
        return
    arg = context.args[0].strip()
    default = _default_account(context, uid)
    acc = resolve_account(default, uid) if default else None
    if not acc:
        await update.message.reply_text("Hesap yok. /connect")
        return
    from . import game_features

    def _board():
        with interactive_account_context(acc):
            return game_features.fetch_war_board(acc.token, acc.name)

    pack = await asyncio.to_thread(_board)
    if not pack.get("ok"):
        await update.message.reply_text(f"❌ {pack.get('error')}")
        return
    numbered = (pack.get("analysis") or {}).get("numbered") or []
    war_id = None
    label = arg
    if arg.isdigit():
        idx = int(arg)
        pick = next((w for w in numbered if w.get("index") == idx), None)
        if pick:
            war_id = str(pick.get("id"))
            label = f"#{idx} {pick.get('display_title')}"
    else:
        war_id = arg
    if not war_id:
        await update.message.reply_text(f"❌ Savaş #{arg} bulunamadı.")
        return
    update_config_field(acc.name, target_war_id=war_id)
    await update.message.reply_text(f"✅ Hedef savaş: {html.escape(label)}", parse_mode="HTML")


@user_required
async def cmd_setstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Örnek:\n"
            "/setstat Kışla, Bilim insanı, Savaş teknikleri\n"
            "veya /setstat Kışla — önce Kışla yükseltilsin"
        )
        return
    uid = _uid(update)
    default = _default_account(context, uid)
    acc = resolve_account(default, uid) if default else None
    if not acc:
        await update.message.reply_text("Hesap yok.")
        return
    arg = " ".join(context.args).strip()
    from . import game_features
    from .stat_board import resolve_active_skill_key, resolve_skill_keys_list, skill_short_name

    def _board():
        with interactive_account_context(acc):
            return game_features.fetch_stat_board(acc.token, acc.name)

    pack = await asyncio.to_thread(_board)
    analysis = pack.get("analysis") or {}

    if "," not in arg:
        skill = resolve_active_skill_key(analysis, arg)
        if skill:
            cfg = get_config(acc.name)
            prio = [s for s in cfg.stat_priority if s != skill]
            prio.insert(0, skill)
            update_config_field(acc.name, stat_priority=prio)
            await update.message.reply_text(
                f"✅ Önce yükseltilen: <b>{html.escape(skill_short_name(skill))}</b>",
                parse_mode="HTML",
            )
            return

    parts = [s.strip() for s in arg.replace(";", ",").split(",") if s.strip()]
    skills = resolve_skill_keys_list(parts, analysis)
    if not skills:
        await update.message.reply_text("Geçersiz stat ismi. Örnek: Kışla, Bilim insanı")
        return
    update_config_field(acc.name, stat_priority=skills)
    names = ", ".join(skill_short_name(s) for s in skills)
    await update.message.reply_text(f"✅ Sıra: {names}")


@user_required
async def cmd_autofarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1 or context.args[0] not in ("on", "off"):
        await update.message.reply_text("/autofarm on|off [isim|all]")
        return
    enabled = context.args[0] == "on"
    target = context.args[1] if len(context.args) > 1 else "all"
    uid = _uid(update)
    accs = _user_accounts(uid) if target == "all" else _resolve_accounts(target, uid)
    for a in accs:
        set_autofarm(a.name, enabled)
    await update.message.reply_text(f"Autofarm {'ON' if enabled else 'OFF'}: {', '.join(a.name for a in accs)}")


@user_required
async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    accs = _resolve_accounts(context.args[0] if context.args else None, uid)
    lines = []
    for a in accs:
        st, d = await _api_for_account(a, game_api.daily_claim)
        lines.append(f"{a.name}: {st} — {str(d)[:120]}")
    await update.message.reply_text("\n".join(lines) if lines else "Hesap yok.")


@user_required
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    accs = _resolve_accounts(context.args[0] if context.args else None, uid)
    lines = []
    for a in accs:
        st, d = await _api_for_account(a, game_api.ping)
        lines.append(f"{a.name}: {st}")
    await update.message.reply_text("\n".join(lines) if lines else "Hesap yok.")


@admin_only
async def cmd_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_pool_status(proxy_assignments()), parse_mode="Markdown")


@admin_only
async def cmd_setproxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("/setproxy isim proxy_id")
        return
    name, proxy_id = context.args[0].lower(), context.args[1]
    slot = get_proxy_by_id(proxy_id)
    if not slot:
        await update.message.reply_text(f"Proxy `{proxy_id}` rules.yaml'da yok.", parse_mode="Markdown")
        return
    if not get_account(name):
        await update.message.reply_text("Hesap bulunamadı.")
        return
    set_proxy(name, slot.id, slot.url)
    await update.message.reply_text(f"✅ {name} → `{slot.id}`", parse_mode="Markdown")


@admin_only
async def cmd_intel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(await asyncio.to_thread(load_intel_summary), parse_mode="Markdown")


@user_required
async def cmd_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rem = cooldown_remaining_sec()
    if rem <= 0:
        await update.message.reply_text("Cooldown yok — istek atılabilir.")
    else:
        await update.message.reply_text(f"429 cooldown: ~{rem}s kaldı.")


@user_required
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    accs = _user_accounts(uid)
    if not accs:
        await update.message.reply_text("Hesap yok.")
        return
    total, lines = 0, ["📊 *Rapor*"]
    for a in accs:
        try:
            p = await _profile_for_account(a)
            total += p.balance
            lines.append(f"{'🟢' if a.autofarm else '⚪'} {a.name}: {p.balance:,} lv{p.level} `{a.proxy_id}`")
        except Exception as e:
            lines.append(f"❌ {a.name}: {e}")
    lines.append(f"\n*Toplam:* {total:,}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_endpoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args) if context.args else ""
    eps = search_endpoints(q, limit=30)
    if not eps:
        await update.message.reply_text("Sonuç yok.")
        return
    lines = [f"`{e['method']}` `{e['path']}`" for e in eps]
    await _reply_long(update, "📚 *API katalog*\n" + "\n".join(lines))


@admin_only
async def cmd_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("/api METHOD /path [hesap] [json_body]")
        return
    method = context.args[0].upper()
    path = context.args[1]
    rest = context.args[2:]
    body = None
    account = _default_account(context, _uid(update))
    for arg in rest:
        if arg.startswith("{"):
            try:
                body = json.loads(arg)
            except json.JSONDecodeError:
                body = json.loads(" ".join(rest[rest.index(arg) :]))
            break
        if not arg.startswith("{"):
            account = arg.lower()
    result = await asyncio.to_thread(
        ai_agent.direct_api, method, path, account, body, allow_confirm=False
    )
    if result.needs_confirmation:
        context.user_data["pending_actions"] = result.pending_actions
    await _reply_long(update, result.reply)


@user_required
async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Örnek: /play bakiyemi göster ve 2 kez farm yap")
        return
    await _run_ai(update, context, text)


@user_required
async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_play(update, context)


async def _run_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    uid = _uid(update)
    default = _default_account(context, uid)

    await update.message.chat.send_action(ChatAction.TYPING)
    from . import intent_router

    acc = resolve_account(default, uid) if default else None

    def _fast():
        if acc:
            with interactive_account_context(acc):
                return intent_router.try_fast_path(text, default)
        return intent_router.try_fast_path(text, default)

    fast = await asyncio.to_thread(_fast)
    if fast is not None:
        if fast.needs_confirmation and fast.pending_actions:
            context.user_data["pending_actions"] = fast.pending_actions
        await _reply_long(
            update,
            fast.reply,
            parse_mode=getattr(fast, "parse_mode", "Markdown"),
            inline_buttons=fast.inline_buttons,
        )
        return

    from .game_coach import answer_teach_full, is_teach_question, local_answer, _topic_match

    status_msg = None
    if is_teach_question(text):
        if not GEMINI_API_KEY:
            taught = await asyncio.to_thread(
                answer_teach_full, text, default, use_gemini=False
            )
            await _reply_long(
                update,
                taught.text,
                parse_mode="Markdown",
                inline_buttons=taught.inline_buttons,
            )
            return
        status_msg = await update.message.reply_text("📚 Koç hazırlanıyor…")
    elif not GEMINI_API_KEY:
        # Yerel koç / konu rehberi — Gemini olmadan
        profile = None
        if acc:
            try:
                def _prof():
                    with interactive_account_context(acc):
                        return game_api.get_profile(acc.token)

                profile = await asyncio.to_thread(_prof)
            except Exception:
                pass
        local = local_answer(text, profile)
        if local:
            from .game_coach import coach_action_buttons

            await _reply_long(
                update,
                local,
                parse_mode="Markdown",
                inline_buttons=coach_action_buttons(profile, _topic_match(text)),
            )
            return
        await update.message.reply_text(
            format_no_ai_fallback_html(),
            parse_mode="HTML",
            reply_markup=no_ai_fallback_markup(),
        )
        return
    else:
        status_msg = await update.message.reply_text("🧠 Gemini planlıyor…")
    try:
        result = await asyncio.to_thread(
            ai_agent.run_agent, text, default or "", telegram_user_id=uid
        )
        if result.needs_confirmation and result.pending_actions:
            context.user_data["pending_actions"] = result.pending_actions
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
        await _reply_long(
            update,
            result.reply,
            parse_mode=getattr(result, "parse_mode", "Markdown"),
            inline_buttons=result.inline_buttons,
        )
    except Exception as e:
        log.exception("ai error")
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
        await update.message.reply_text(
            f"❌ İşlem tamamlanamadı.\n\n{format_no_ai_fallback_html()}",
            parse_mode="HTML",
            reply_markup=no_ai_fallback_markup(),
        )


@user_required
async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_actions")
    if not pending:
        await update.message.reply_text("Bekleyen işlem yok.")
        return
    result = await asyncio.to_thread(
        ai_agent.run_confirmed, pending, _default_account(context, _uid(update))
    )
    context.user_data.pop("pending_actions", None)
    await _reply_long(update, result.reply)


@user_required
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_actions", None)
    await update.message.reply_text("İptal edildi.")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from . import callbacks
    query = update.callback_query
    if not query or not query.data:
        return
    uid = _uid(update)
    if not bot_allows_user(uid):
        await query.answer("Bot kapalı modda", show_alert=True)
        return

    data = query.data
    default = _default_account(context, _uid(update))

    try:
        await query.answer(_callback_toast(data))
    except Exception:
        pass

    try:
        await callbacks.handle_callback(update, context, data, default, query, uid)
    except Exception as e:
        log.exception("callback %s: %s", data, e)
        send_crash_notify(
            "Callback hatası",
            f"data={data}",
            exc=e,
            update_summary=summarize_update(update),
            dedupe_key=f"callback:{data}:{type(e).__name__}",
        )
        try:
            await _loading_edit(query, f"❌ {USER_FACING_ERROR}")
            if query.message:
                await query.message.edit_reply_markup(reply_markup=result_with_home_markup())
        except Exception:
            pass


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    uid = _uid(update)
    if not bot_allows_user(uid):
        return

    text = update.message.text.strip()
    if text.startswith("eyJ"):
        pending = context.user_data.pop("pending_add", None)
        if not pending and _session_pending_connect(context, uid):
            pending = default_account_name(uid)
        if not pending and not _user_accounts(uid):
            pending = default_account_name(uid)
        if pending:
            await _save_account(update, pending, text, uid=uid, context=context)
            return

    mapped = normalize_menu_text(text)
    if mapped:
        await _dispatch_menu(update, context, mapped)
        return

    if len(text) < 3 or text.startswith("/"):
        return

    await _run_ai(update, context, text)


async def _notify_admins_on_start(application: Application) -> None:
    """Bot ayağa kalkınca adminlere tek seferlik ping (önceden /start yapmış olmalılar)."""
    if not TELEGRAM_ADMIN_IDS:
        return
    text = (
        f"✅ <b>Diplomacia Bot {get_version_label()}</b> Hetzner'da çalışıyor.\n"
        "Komutlar: /dashboard · /start\n"
        "<i>Windows'taki eski botu kapat — aynı token 409 Conflict üretir.</i>"
    )
    for uid in TELEGRAM_ADMIN_IDS:
        try:
            await application.bot.send_message(
                chat_id=uid,
                text=text,
                parse_mode="HTML",
                reply_markup=main_reply_keyboard(),
            )
        except Exception as e:
            log.warning("Admin ping %s başarısız: %s", uid, e)


async def _post_init(application: Application) -> None:
    await setup_bot_ui(application)
    await _notify_admins_on_start(application)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, Conflict):
        msg = "409 Conflict: başka makinede aynı token ile polling (Windows botu kapat)"
        log.error(msg)
        send_crash_notify(
            "Telegram 409 Conflict",
            msg,
            exc=err,
            update_summary=summarize_update(update),
            dedupe_key="conflict:409",
        )
        return
    log.exception("Handler hatası", exc_info=err)
    if err:
        send_crash_notify(
            "Handler hatası",
            "Komut/callback işlenirken exception",
            exc=err if isinstance(err, BaseException) else None,
            update_summary=summarize_update(update),
            dedupe_key=f"handler:{type(err).__name__}:{str(err)[:60]}",
        )


async def stat_queue_job(context: ContextTypes.DEFAULT_TYPE):
    """Stat kuyruk — cooldown bitince ~15 sn içinde sonraki yükseltme."""
    from .stat_queue import accounts_for_stat_queue, tick_stat_queue

    for acc in accounts_for_stat_queue():
        try:
            await asyncio.to_thread(tick_stat_queue, acc)
        except Exception as e:
            log.exception("stat_queue %s: %s", acc.name, e)


async def press_like_job(context: ContextTypes.DEFAULT_TYPE):
    """auto_like_articles açık hesaplar için yeni makaleleri beğen (~5 dk)."""
    from .account_config import get_config
    from .press_likes import auto_like_articles, format_like_result_html
    from .store import list_accounts

    for acc in list_accounts():
        cfg = get_config(acc.name)
        if not cfg.auto_like_articles:
            continue
        try:
            res = await asyncio.to_thread(auto_like_articles, acc.token, acc.name)
        except Exception as e:
            log.warning("press_like %s: %s", acc.name, e)
            continue
        # Beğeni olduysa (veya hata varsa) kullanıcıya bildir; beğenilen yoksa sessiz.
        if res.get("liked", 0) > 0 or res.get("errors", 0) > 0:
            notify_uid = acc.telegram_user_id or (next(iter(TELEGRAM_ADMIN_IDS)) if TELEGRAM_ADMIN_IDS else None)
            if notify_uid:
                try:
                    await context.bot.send_message(
                        chat_id=notify_uid,
                        text=format_like_result_html(res),
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass


async def autofarm_job(context: ContextTypes.DEFAULT_TYPE):
    from .fleet_live import format_tick_line
    from .fleet_manager import tick_one

    rules = load_rules()
    due = list(autofarm_due(AUTOFARM_INTERVAL_SEC))
    for i, acc in enumerate(due):
        if normalize_role(get_config(acc.name).role) == "off":
            continue
        if i > 0:
            await asyncio.sleep(rules.stagger_farm_sec)
        try:
            r = await asyncio.to_thread(tick_one, acc)
            log_action(
                "autofarm",
                account_name=acc.name,
                telegram_user_id=acc.telegram_user_id,
                result=f"ok={r.ok} balance={getattr(r, 'balance_after', 0)}",
                success=bool(r.ok),
            )
            notify_uid = acc.telegram_user_id or (next(iter(TELEGRAM_ADMIN_IDS)) if TELEGRAM_ADMIN_IDS else None)
            if notify_uid:
                tag = role_label(get_config(acc.name).role)
                line = format_tick_line(acc, r)
                await context.bot.send_message(
                    chat_id=notify_uid,
                    text=f"🤖 Autofarm [{tag}]\n{line}",
                )
        except Exception as e:
            log.exception("autofarm %s: %s", acc.name, e)
            send_crash_notify(
                f"Autofarm hatası ({acc.name})",
                str(e)[:500],
                exc=e,
                dedupe_key=f"autofarm:{acc.name}:{type(e).__name__}",
            )


def run() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN eksik")

    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    init_db()
    boot = bootstrap_legacy()
    if boot:
        log.info("Legacy import: %s", boot.name)
    if GEMINI_API_KEY:
        from .gemini_client import verify_connection

        try:
            probe = verify_connection()
            log.info(
                "Gemini OK: %s (%sms)",
                probe.get("model"),
                probe.get("latency_ms"),
            )
        except Exception as e:
            log.warning("Gemini smoke failed: %s", e)

    else:
        log.warning("GEMINI_API_KEY yok — AI devre dışı")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .post_init(_post_init)
        .build()
    )
    for name, handler in [
        ("start", cmd_start),
        ("connect", cmd_connect),
        ("menu", cmd_menu),
        ("dashboard", cmd_dashboard),
        ("fleet", cmd_fleet),
        ("setrole", cmd_setrole),
        ("settings", cmd_settings),
        ("help", cmd_help),
        ("whoami", cmd_whoami),
        ("version", cmd_version),
        ("setaccount", cmd_setaccount),
        ("accounts", cmd_accounts),
        ("add", cmd_add),
        ("remove", cmd_remove),
        ("status", cmd_status),
        ("farm", cmd_farm),
        ("setfabric", cmd_setfabric),
        ("setwar", cmd_setwar),
        ("setstat", cmd_setstat),
        ("plan", cmd_plan),
        ("autofarm", cmd_autofarm),
        ("daily", cmd_daily),
        ("ping", cmd_ping),
        ("report", cmd_report),
        ("proxies", cmd_proxies),
        ("setproxy", cmd_setproxy),
        ("intel", cmd_intel),
        ("cooldown", cmd_cooldown),
        ("endpoints", cmd_endpoints),
        ("api", cmd_api),
        ("play", cmd_play),
        ("ai", cmd_ai),
        ("confirm", cmd_confirm),
        ("cancel", cmd_cancel),
    ]:
        app.add_handler(CommandHandler(name, handler))

    app.add_handler(CallbackQueryHandler(on_callback, block=False))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text, block=False))
    app.add_error_handler(_on_error)

    if app.job_queue:
        from .config import STAT_QUEUE_INTERVAL_SEC

        app.job_queue.run_repeating(stat_queue_job, interval=STAT_QUEUE_INTERVAL_SEC, first=15)
        app.job_queue.run_repeating(autofarm_job, interval=60, first=30)
        app.job_queue.run_repeating(press_like_job, interval=300, first=60)

    log.info("Bot %s başlıyor…", get_version_label())
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


# test_telegram_app_import.py + geri-uyumlu re-export
from .callbacks import handle_callback as _handle_callback
