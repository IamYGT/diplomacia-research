from __future__ import annotations

import asyncio
import json
import logging
from functools import wraps
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from . import ai_agent, farmer, game_api
from .account_pool import format_pool_status, get_proxy_by_id, load_intel_summary, load_rules, suggest_proxy
from .account_runtime import account_context, run_for_account
from .catalog import search_endpoints
from .config import AUTOFARM_INTERVAL_SEC, GEMINI_API_KEY, TELEGRAM_ADMIN_IDS, TELEGRAM_BOT_TOKEN
from .stealth_client import cooldown_remaining_sec
from .account_config import AccountConfig, get_config, update_config_field
from .store import (
    Account,
    add_account,
    autofarm_due,
    bootstrap_legacy,
    get_account,
    init_db,
    list_accounts,
    proxy_assignments,
    remove_account,
    set_autofarm,
    set_proxy,
    update_after_farm,
)

from .version import get_version_label

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


def admin_only(func: Callable):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else 0
        if TELEGRAM_ADMIN_IDS and uid not in TELEGRAM_ADMIN_IDS:
            await update.message.reply_text(
                f"⛔ Yetkisiz. Telegram ID'n: `{uid}`",
                parse_mode="Markdown",
            )
            return
        return await func(update, context)

    return wrapper


def _resolve_accounts(arg: str | None) -> list[Account]:
    if not arg or arg.lower() == "all":
        return list_accounts()
    acc = get_account(arg)
    return [acc] if acc else []


def _default_account(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("default_account") or "ercan2"


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


@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    ai = "🧠 Gemini bağlı" if GEMINI_API_KEY else "⚠️ GEMINI_API_KEY yok"
    await update.message.reply_text(
        f"Diplomacia AI bot {get_version_label()} aktif.\nID: `{uid}` | {ai}\n\n/help",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 Diplomacy YGT Bot *{get_version_label()}*\n"
        f"Modüller: economy, factory, stats, training, war, orchestrator\n"
        f"Changelog: `bot/CHANGELOG.md`",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_long(update, HELP_TEXT)


@admin_only
async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    await update.message.reply_text(f"Telegram user ID: `{uid}`", parse_mode="Markdown")


@admin_only
async def cmd_setaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"Varsayılan: `{_default_account(context)}`", parse_mode="Markdown")
        return
    name = context.args[0].lower()
    if not get_account(name):
        await update.message.reply_text("Hesap bulunamadı.")
        return
    context.user_data["default_account"] = name
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


@admin_only
async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accs = list_accounts()
    if not accs:
        await update.message.reply_text("Henüz hesap yok. /add ercan2")
        return
    default = _default_account(context)
    lines = []
    for a in accs:
        mark = "⭐" if a.name == default else "•"
        af = "🟢" if a.autofarm else "⚪"
        px = a.proxy_id or "direct"
        lines.append(f"{mark} *{a.name}* — {a.username} | {a.last_balance:,}₺ | {af} | `{px}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /add isim\nSonra JWT veya /add isim JWT")
        return
    name = context.args[0].lower()
    token = " ".join(context.args[1:]).strip()
    if not token:
        context.user_data["pending_add"] = name
        await update.message.reply_text(f"`{name}` için JWT yapıştır.", parse_mode="Markdown")
        return
    await _save_account(update, name, token)


async def _save_account(update: Update, name: str, token: str):
    try:
        slot = suggest_proxy(proxy_assignments())

        def _fetch():
            with account_context(proxy_id=slot.id, proxy_url=slot.url or None):
                return game_api.get_profile(token)

        prof = await asyncio.to_thread(_fetch)
        acc = add_account(name, token, prof.player_id, prof.username, slot.id, slot.url)
        await update.message.reply_text(
            f"✅ *{acc.name}* → {prof.username}\n💰 {prof.balance:,} | lv{prof.level} | proxy `{slot.id}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@admin_only
async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/remove isim")
        return
    if remove_account(context.args[0]):
        await update.message.reply_text("Silindi.")
    else:
        await update.message.reply_text("Bulunamadı.")


@admin_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accs = _resolve_accounts(context.args[0] if context.args else None) or list_accounts()
    if not accs:
        await update.message.reply_text("Hesap yok.")
        return
    lines = []
    for a in accs:
        try:
            p = await _profile_for_account(a)
            lines.append(
                f"*{a.name}* ({p.username}) `{a.proxy_id}`\n💰 {p.balance:,} | 💎 {p.diamonds} | lv{p.level} | ❤️ {p.health}"
            )
        except Exception as e:
            lines.append(f"*{a.name}*: {e}")
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cycles, name_arg = 1, None
    if context.args:
        if context.args[0].isdigit():
            cycles = int(context.args[0])
            name_arg = context.args[1] if len(context.args) > 1 else None
        else:
            name_arg = context.args[0]
    accs = _resolve_accounts(name_arg) or list_accounts()
    if not accs:
        await update.message.reply_text("Hesap yok.")
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


@admin_only
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
    if not get_account(name):
        await update.message.reply_text("Hesap bulunamadı.")
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


@admin_only
async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accs = _resolve_accounts(context.args[0] if context.args else None) or list_accounts()
    if not accs:
        await update.message.reply_text("Hesap yok.")
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


@admin_only
async def cmd_autofarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1 or context.args[0] not in ("on", "off"):
        await update.message.reply_text("/autofarm on|off [isim|all]")
        return
    enabled = context.args[0] == "on"
    target = context.args[1] if len(context.args) > 1 else "all"
    accs = list_accounts() if target == "all" else _resolve_accounts(target)
    for a in accs:
        set_autofarm(a.name, enabled)
    await update.message.reply_text(f"Autofarm {'ON' if enabled else 'OFF'}: {', '.join(a.name for a in accs)}")


@admin_only
async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accs = _resolve_accounts(context.args[0] if context.args else None) or list_accounts()
    lines = []
    for a in accs:
        st, d = await _api_for_account(a, game_api.daily_claim)
        lines.append(f"{a.name}: {st} — {str(d)[:120]}")
    await update.message.reply_text("\n".join(lines) if lines else "Hesap yok.")


@admin_only
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accs = _resolve_accounts(context.args[0] if context.args else None) or list_accounts()
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


@admin_only
async def cmd_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rem = cooldown_remaining_sec()
    if rem <= 0:
        await update.message.reply_text("Cooldown yok — istek atılabilir.")
    else:
        await update.message.reply_text(f"429 cooldown: ~{rem}s kaldı.")


@admin_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accs = list_accounts()
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
    account = _default_account(context)
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


@admin_only
async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Örnek: /play bakiyemi göster ve 2 kez farm yap")
        return
    await _run_ai(update, context, text)


@admin_only
async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_play(update, context)


async def _run_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    default = _default_account(context)
    from . import intent_router

    fast = await asyncio.to_thread(intent_router.try_fast_path, text, default)
    if fast is not None:
        if fast.needs_confirmation and fast.pending_actions:
            context.user_data["pending_actions"] = fast.pending_actions
        await _reply_long(update, fast.reply, inline_buttons=fast.inline_buttons)
        return

    from .game_coach import is_teach_question

    if is_teach_question(text):
        await update.message.reply_text("📚 Koç hazırlanıyor...")
    elif not GEMINI_API_KEY:
        await update.message.reply_text("GEMINI_API_KEY yok. `farm yap` / `ne durumdayım` kullan.")
        return
    else:
        await update.message.reply_text("🧠 Gemini planlıyor...")
    try:
        result = await asyncio.to_thread(ai_agent.run_agent, text, default)
        if result.needs_confirmation and result.pending_actions:
            context.user_data["pending_actions"] = result.pending_actions
        await _reply_long(update, result.reply, inline_buttons=result.inline_buttons)
    except Exception as e:
        log.exception("ai error")
        await update.message.reply_text(f"❌ {e}\n\nDene: `farm yap` veya `/status`")


@admin_only
async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_actions")
    if not pending:
        await update.message.reply_text("Bekleyen işlem yok.")
        return
    result = await asyncio.to_thread(
        ai_agent.run_confirmed, pending, _default_account(context)
    )
    context.user_data.pop("pending_actions", None)
    await _reply_long(update, result.reply)


@admin_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_actions", None)
    await update.message.reply_text("İptal edildi.")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if TELEGRAM_ADMIN_IDS and uid not in TELEGRAM_ADMIN_IDS:
        await query.answer("Yetkisiz", show_alert=True)
        return
    await query.answer()
    data = query.data
    default = _default_account(context)

    acc = get_account(default)
    if not acc:
        await query.edit_message_text("Hesap yok.")
        return

    if data.startswith("country:"):
        country_id = data.split(":", 1)[1]
        try:
            from .response_format import format_country_result

            result = await asyncio.to_thread(run_for_account, acc, game_api.select_country, acc.token, country_id)
            await query.edit_message_text(format_country_result(result), parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Ülke seçilemedi: {e}")
        return

    if data == "action:hap":
        try:
            from .response_format import format_pills

            result = await asyncio.to_thread(run_for_account, acc, game_api.use_pills, acc.token)
            await query.edit_message_text(format_pills(result), parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ {e}")
        return

    if data in ("action:farm", "action:smartfarm"):
        r = await asyncio.to_thread(
            farmer.run_farm, acc.token, acc.name, 1, acc.proxy_url or None, acc.proxy_id or ""
        )
        update_after_farm(acc.name, r.balance_after)
        await query.edit_message_text(farmer.format_farm_result(r), parse_mode="Markdown")
        return

    if data == "action:status":
        from .dynamic_context import format_plan_summary

        p = await _profile_for_account(acc)
        await query.edit_message_text(
            format_plan_summary(acc.name) + f"\n\n💰 {p.balance:,} | 💎 {p.diamonds} | lv{p.level}",
            parse_mode="Markdown",
        )
        return

    if data == "action:quests":
        from .response_format import format_quest_claims

        results = await asyncio.to_thread(run_for_account, acc, game_api.claim_ready_quests, acc.token)
        await query.edit_message_text(format_quest_claims(results), parse_mode="Markdown")
        return


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if TELEGRAM_ADMIN_IDS and uid not in TELEGRAM_ADMIN_IDS:
        return

    text = update.message.text.strip()
    pending = context.user_data.get("pending_add")
    if pending and text.startswith("eyJ"):
        context.user_data.pop("pending_add", None)
        await _save_account(update, pending, text)
        return

    if len(text) < 3 or text.startswith("/"):
        return

    await _run_ai(update, context, text)


async def autofarm_job(context: ContextTypes.DEFAULT_TYPE):
    rules = load_rules()
    due = list(autofarm_due(AUTOFARM_INTERVAL_SEC))
    for i, acc in enumerate(due):
        if i > 0:
            await asyncio.sleep(rules.stagger_farm_sec)
        try:
            r = await asyncio.to_thread(
                farmer.run_farm, acc.token, acc.name, 1, acc.proxy_url or None, acc.proxy_id or ""
            )
            update_after_farm(acc.name, r.balance_after)
            if r.earned_money > 0 and TELEGRAM_ADMIN_IDS:
                await context.bot.send_message(
                    chat_id=next(iter(TELEGRAM_ADMIN_IDS)),
                    text=f"🤖 Autofarm\n{farmer.format_farm_result(r)}",
                )
        except Exception as e:
            log.exception("autofarm %s: %s", acc.name, e)


def run() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN eksik")

    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    init_db()
    boot = bootstrap_legacy()
    if boot:
        log.info("Legacy import: %s", boot.name)
    if GEMINI_API_KEY:
        log.info("Gemini model: %s", __import__("diplomacy_bot.config", fromlist=["GEMINI_MODEL"]).GEMINI_MODEL)
    else:
        log.warning("GEMINI_API_KEY yok — AI devre dışı")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    for name, handler in [
        ("start", cmd_start),
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

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if app.job_queue:
        app.job_queue.run_repeating(autofarm_job, interval=60, first=30)

    log.info("Bot v2 başlıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
