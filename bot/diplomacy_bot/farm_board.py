"""Farm merkezi — work, elmas→hap döngüsü, ROI ve interaktif aksiyonlar."""

from __future__ import annotations

import html
from typing import Any

from .account_config import AccountConfig
from .feature_analysis import analyze_auto_status, analyze_craft
from .modules.economy import DIAMONDS_PER_WORK
from .user_errors import format_ms

CRAFT_PRESETS = (500, 1000, 1500, 3000)


def _next_action(
    *,
    work_ready: bool,
    work_ms: int,
    health: int,
    pills: int,
    pill_ready: bool,
    pill_ms: int,
    diamonds: int,
    cfg: AccountConfig,
    craft_can: bool,
) -> tuple[str, str]:
    """(action_key, tr_label)"""
    if work_ms > 0:
        return "wait_work", f"Work bekle — {format_ms(work_ms)}"
    if health < 100 and pills > 0 and not pill_ready and pill_ms > 0:
        return "wait_pill", f"Hap CD — {format_ms(pill_ms)}"
    if health < 100 and pills > 0:
        return "use_pill", "Önce can doldur (hap)"
    if health <= 0 and pills <= 0:
        return "craft", "Can 0 — elmas→hap craft gerekli"
    if craft_can and cfg.craft_pills_when_low and pills < cfg.min_pill_stock:
        return "craft", f"Hap stok < {cfg.min_pill_stock} — craft önerilir"
    if work_ready:
        return "work", "Fabrikada çalış (+elmas)"
    return "idle", "Hazır — döngüyü başlat"


def _analysis_health(analysis: dict) -> int:
    h = analysis.get("health")
    return int(h) if h is not None else 0


def _pill_status_alert(analysis: dict) -> str:
    """Can düşük / hap CD — üst uyarı bloğu."""
    health = _analysis_health(analysis)
    pill_ms = int(analysis.get("pill_ms") or 0)
    pills = int(analysis.get("pills") or 0)
    if health >= 100:
        return ""
    if pills <= 0:
        return f"🚨 <b>Can {health}/100</b> — hap yok, elmas→hap craft gerekli"
    if not analysis.get("pill_ready") and pill_ms > 0:
        return (
            f"🚨 <b>Can {health}/100 — farm durdu</b>\n"
            f"⏳ Hap bekleme: <b>{format_ms(pill_ms)}</b> · sonra 💊 Can Doldur"
        )
    return f"💊 <b>Can {health}/100</b> — önce Can Doldur, sonra çalış"


def _work_status_line(analysis: dict) -> str:
    """Fabrika/work satırı — can 0 + working API uyumsuzluğu."""
    h_raw = analysis.get("health")
    health = int(h_raw) if h_raw is not None else 100
    if analysis.get("working"):
        fid = html.escape(str(analysis.get("work_factory_id") or "?"))
        if health < 100:
            return (
                f"⚙️ Sunucu fabrikada gösteriyor: <code>{fid}</code>\n"
                f"<i>❤️ Can {health}/100 — kazanç için önce hap gerekebilir</i>"
            )
        return f"⚙️ Fabrikada çalışıyor: <code>{fid}</code>"
    if analysis.get("work_ready"):
        return "✅ <b>Work hazır</b> — çalışabilirsin"
    return f"⏳ Work CD: <b>{format_ms(analysis.get('work_ms'))}</b>"


def _show_farm_roi(analysis: dict) -> bool:
    """Can düşük + sunucu working — kazanç tahmini yanıltıcı."""
    if _analysis_health(analysis) < 100 and analysis.get("working"):
        return False
    return True


def analyze_farm_board_enriched(
    pack: dict,
    cfg: AccountConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or AccountConfig("x")
    auto = pack.get("auto") or {}
    prof = pack.get("profile") or {}
    work_st = pack.get("work") or {}

    if hasattr(prof, "diamonds"):
        diamonds = int(prof.diamonds or 0)
        pills_prof = int(prof.health_pills or 0)
        balance = int(prof.balance or 0)
        health_prof = int(prof.health or 0)
        username = prof.username
    else:
        diamonds = int(prof.get("diamonds") or 0)
        pills_prof = int(prof.get("health_pills") or 0)
        balance = int(prof.get("balance") or 0)
        health_prof = int(prof.get("health") or 0)
        username = prof.get("username") or "?"

    aa = analyze_auto_status(auto, profile_health=health_prof)
    craft_profile = {
        "diamonds": diamonds,
        "health_pills": aa.get("pills") or pills_prof,
    }
    craft_a = analyze_craft(craft_profile, auto, cfg)

    work_ms = int(aa.get("work_ms") or 0)
    pill_ms = int(aa.get("pill_ms") or 0)
    health = int(aa.get("health") or 0)
    pills = int(aa.get("pills") or pills_prof)
    working = bool(work_st.get("working"))
    work_factory_id = work_st.get("factory_id") or work_st.get("current_factory_id")

    batch = int(cfg.craft_diamond_batch or 3000)
    suggested = int(craft_a.get("suggested_batch") or 0)
    breakeven = (suggested // DIAMONDS_PER_WORK) if suggested and DIAMONDS_PER_WORK else 0
    works_per_day_est = 120
    daily_diamond_est = works_per_day_est * DIAMONDS_PER_WORK

    action_key, action_label = _next_action(
        work_ready=bool(aa.get("work_ready")),
        work_ms=work_ms,
        health=health,
        pills=pills,
        pill_ready=bool(aa.get("pill_ready")),
        pill_ms=pill_ms,
        diamonds=diamonds,
        cfg=cfg,
        craft_can=bool(craft_a.get("can_craft")),
    )

    presets = []
    for p in CRAFT_PRESETS:
        if p <= diamonds:
            presets.append(p)
    if suggested and suggested not in presets and suggested <= diamonds:
        presets.append(suggested)
    presets = sorted(set(presets))[:5]

    tips: list[str] = []
    if health < 100 and not aa.get("pill_ready") and pill_ms > 0:
        tips.append(f"🚨 Farm beklemede — hap CD {format_ms(pill_ms)}")
    if work_ms > 0:
        tips.append(f"Work CD: {format_ms(work_ms)} — beklerken stat/görev yap")
    if craft_a.get("can_craft"):
        tips.append(
            f"{suggested} elmas → hap · ~{breakeven} work ile elmas geri (~{DIAMONDS_PER_WORK}/work)"
        )
    if diamonds < batch and pills < cfg.min_pill_stock:
        tips.append("Elmas düşük — önce work veya günlük ödül")
    if not cfg.craft_pills_when_low:
        tips.append("Otomatik craft kapalı — 💎 butonlarıyla manuel üret")

    return {
        **aa,
        **craft_a,
        "username": username,
        "balance": balance,
        "diamonds": diamonds,
        "health": health,
        "pills": pills,
        "working": working,
        "work_factory_id": work_factory_id,
        "work_mode": cfg.work_mode,
        "craft_pills_when_low": cfg.craft_pills_when_low,
        "min_pill_stock": cfg.min_pill_stock,
        "craft_batch_cfg": batch,
        "craft_presets": presets,
        "next_action": action_key,
        "next_action_label": action_label,
        "breakeven_works": breakeven,
        "diamonds_per_work": DIAMONDS_PER_WORK,
        "daily_diamond_est": daily_diamond_est,
        "roi_note": craft_a.get("roi_note") or f"~{DIAMONDS_PER_WORK} elmas/work",
        "tips": tips[:4],
        "can_work": bool(aa.get("work_ready")) and health > 0,
        "can_craft_manual": diamonds >= 500,
        "can_use_pill": health < 100 and pills > 0 and bool(aa.get("pill_ready")),
    }


def format_farm_board_html(
    pack: dict,
    analysis: dict | None = None,
    cfg: AccountConfig | None = None,
) -> str:
    cfg = cfg or AccountConfig("x")
    if analysis is None:
        analysis = analyze_farm_board_enriched(pack, cfg)

    uname = html.escape(str(analysis.get("username") or "?"))
    lines = [
        f"<b>🌾 Farm merkezi</b> — {uname}",
        f"💰 {int(analysis.get('balance') or 0):,}₺ · 💎 {analysis.get('diamonds', 0):,} · "
        f"❤️ {analysis.get('health', '?')}/100 · 💊 {analysis.get('pills', '?')}",
    ]
    alert = _pill_status_alert(analysis)
    if alert:
        lines.append(alert)

    lines.append(_work_status_line(analysis))

    if not analysis.get("pill_ready") and int(analysis.get("pill_ms") or 0) > 0:
        lines.append(f"⏳ Hap CD: <b>{format_ms(analysis.get('pill_ms'))}</b>")

    if _show_farm_roi(analysis):
        lines.append(
            f"\n<b>💎↔️💊 Elmas–hap döngüsü</b>\n"
            f"• Work başına ~<b>{analysis.get('diamonds_per_work')}</b> elmas\n"
            f"• Önerilen craft: <b>{analysis.get('suggested_batch', 0)}</b> elmas "
            f"(DB batch: {analysis.get('craft_batch_cfg')})\n"
            f"• Başabaş: ~<b>{analysis.get('breakeven_works')}</b> work · "
            f"gün tahmini ~{analysis.get('daily_diamond_est', 0):,} elmas"
        )
        lines.append(
            f"Hap hedef: {analysis.get('min_pill_stock')} · "
            f"Otomatik craft: {'açık' if analysis.get('craft_pills_when_low') else 'kapalı'}"
        )
    else:
        lines.append(
            "\n<i>💡 Can düşükken kazanç tahmini gizlendi — önce 💊 Can Doldur</i>"
        )

    lines.append(f"\n<b>🎯 Sıradaki:</b> {html.escape(str(analysis.get('next_action_label')))}")

    for tip in analysis.get("tips", [])[:3]:
        lines.append(f"💡 {html.escape(str(tip))}")

    lines.append(
        "\n<i>🌾 work · 💎 craft · 💊 can · 🧠 akıllı döngü · batch DB'ye kaydedilir</i>"
    )
    return "\n".join(lines)


def format_farm_action_html(result: dict) -> str:
    action = html.escape(str(result.get("action") or "farm"))
    if result.get("ok"):
        msg = html.escape(str(result.get("message") or "Tamam")[:300])
        extra = ""
        if result.get("earned_money"):
            extra += f"\n+{result['earned_money']:,}₺"
        if result.get("earned_diamonds"):
            extra += f" · +{result['earned_diamonds']}💎"
        if result.get("crafted"):
            extra += f"\n💎→💊 {result['crafted']} elmas craft"
        if result.get("factory_id"):
            extra += f"\n🏭 <code>{html.escape(str(result['factory_id']))}</code>"
        return f"<b>🌾 {action}</b> ✅\n{msg}{extra}"
    if result.get("farm_result"):
        from .feature_reports import format_farm_html

        return format_farm_html(result["farm_result"])
    err = html.escape(str(result.get("error") or "?")[:280])
    return f"<b>🌾 {action}</b> ❌\n{err}"


def farm_board_inline_markup(analysis: dict) -> "InlineKeyboardMarkup":
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    from .telegram_ui import back_home_button

    a = analysis or {}
    rows: list[list] = []

    work_ready = bool(a.get("can_work"))
    work_ms = int(a.get("work_ms") or 0)
    if work_ready:
        rows.append(
            [
                InlineKeyboardButton("🌾 Çalış", callback_data="farm:work"),
                InlineKeyboardButton("🧠 Akıllı döngü", callback_data="farm:smart"),
            ]
        )
    else:
        label = f"⏳ Work {format_ms(work_ms)}" if work_ms else "⏳ Work bekle"
        rows.append(
            [
                InlineKeyboardButton(label, callback_data="action:farmboard"),
                InlineKeyboardButton("🧠 Akıllı döngü", callback_data="farm:smart"),
            ]
        )

    craft_row: list = []
    for p in (a.get("craft_presets") or CRAFT_PRESETS)[:4]:
        craft_row.append(
            InlineKeyboardButton(f"💎{p}", callback_data=f"farm:craft:{p}")
        )
    batch = int(a.get("craft_batch_cfg") or 3000)
    if batch not in [int(x) for x in (a.get("craft_presets") or [])]:
        craft_row.append(InlineKeyboardButton(f"⭐{batch}", callback_data=f"farm:craft:{batch}"))
    if craft_row:
        rows.append(craft_row[:4])

    pill_ms = int(a.get("pill_ms") or 0)
    h_raw = a.get("health")
    health = int(h_raw) if h_raw is not None else 100
    if a.get("can_use_pill"):
        pill_btn = InlineKeyboardButton("💊 Can doldur", callback_data="farm:hap")
    elif health < 100 and pill_ms > 0:
        pill_btn = InlineKeyboardButton(f"⏳ Hap {format_ms(pill_ms)}", callback_data="action:farmboard")
    else:
        pill_btn = InlineKeyboardButton("💊 Can doldur", callback_data="farm:hap")

    rows.append(
        [
            pill_btn,
            InlineKeyboardButton(
                "🔁 Oto craft " + ("✓" if a.get("craft_pills_when_low") else "✗"),
                callback_data="farm:toggle:autocraft",
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🏭 Fabrika", callback_data="action:myfactory"),
            InlineKeyboardButton("🔄 Yenile", callback_data="action:farmboard"),
            back_home_button(),
        ]
    )
    return InlineKeyboardMarkup(rows)


def farm_board_callback_rows(analysis: dict) -> list[list[tuple[str, str]]]:
    a = analysis or {}
    rows: list[list[tuple[str, str]]] = []
    if a.get("can_work"):
        rows.append([("🌾 Çalış", "farm:work"), ("🧠 Akıllı döngü", "farm:smart")])
    else:
        rows.append([("🧠 Akıllı döngü", "farm:smart")])
    craft: list[tuple[str, str]] = []
    for p in (a.get("craft_presets") or [1000, 3000])[:3]:
        craft.append((f"💎{p}", f"farm:craft:{p}"))
    if craft:
        rows.append(craft)
    rows.append([("💊 Can", "farm:hap"), ("🔄 Yenile", "action:farmboard")])
    rows.append([("🏠 Ana Sayfa", "dash:home")])
    return rows
