"""Fabrika merkezi — zenginleştirme, format ve inline aksiyonlar."""

from __future__ import annotations

import html
import re
from typing import Any

from .account_config import AccountConfig
from .feature_analysis import analyze_factories
from .user_errors import format_ms

WORK_MODE_LABELS = {
    "own": "Kendi",
    "foreign": "Yabancı",
    "fixed": "Sabit",
    "auto": "Otomatik",
}


def _parse_int(val: Any) -> int:
    try:
        return int(str(val or "0").replace(",", "").replace(".", ""))
    except (ValueError, TypeError):
        return 0


def _factory_id(f: dict) -> str:
    return str(f.get("id") or f.get("factory_id") or "")


def _type_label(t: str | None) -> str:
    m = {
        "elmas": "💎 Elmas",
        "altin": "🥇 Altın",
        "petrol": "🛢 Petrol",
        "demir": "⚙️ Demir",
    }
    return m.get((t or "").lower(), t or "?")


def _is_closed(f: dict) -> bool:
    if f.get("is_closed") is True:
        return True
    st = str(f.get("status") or "").lower()
    return st in ("closed", "kapali", "kapalı")


def enrich_owned(
    f: dict,
    *,
    index: int,
    cfg: AccountConfig,
    work_factory_id: str | None,
) -> dict[str, Any]:
    fid = _factory_id(f)
    workers = _parse_int(f.get("worker_count") or f.get("workers"))
    balance = _parse_int(
        f.get("balance")
        or f.get("stored_money")
        or f.get("money_balance")
        or f.get("accumulated")
    )
    salary = f.get("salary_rate") or f.get("salary") or f.get("wage")
    return {
        **f,
        "index": index,
        "list": "owned",
        "factory_id": fid,
        "display_name": str(f.get("name") or f"Fabrika {index}"),
        "type_label": _type_label(f.get("type")),
        "level_int": _parse_int(f.get("level")),
        "workers_int": workers,
        "balance_int": balance,
        "salary_pct": salary,
        "province_label": str(f.get("province_name") or f.get("region") or "?"),
        "is_closed": _is_closed(f),
        "is_primary": bool(cfg.primary_factory_id and fid == cfg.primary_factory_id),
        "is_preferred": bool(cfg.preferred_factory_id and fid == cfg.preferred_factory_id),
        "is_working_here": bool(work_factory_id and fid == work_factory_id),
    }


def enrich_region(
    f: dict,
    *,
    index: int,
    cfg: AccountConfig,
    work_factory_id: str | None,
) -> dict[str, Any]:
    fid = _factory_id(f)
    return {
        **f,
        "index": index,
        "list": "region",
        "factory_id": fid,
        "display_name": str(f.get("name") or "?"),
        "owner_label": str(f.get("owner_name") or f.get("username") or "?"),
        "type_label": _type_label(f.get("type")),
        "level_int": _parse_int(f.get("level")),
        "salary_pct": f.get("salary_rate") or f.get("salary"),
        "province_label": str(f.get("province_name") or f.get("region") or "?"),
        "is_preferred": bool(cfg.preferred_factory_id and fid == cfg.preferred_factory_id),
        "is_working_here": bool(work_factory_id and fid == work_factory_id),
        "score_hint": _parse_int(f.get("salary_rate")) + _parse_int(f.get("level")) * 2,
    }


def analyze_factory_board_enriched(
    pack: dict,
    cfg: AccountConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or AccountConfig("x")
    factories = list(pack.get("factories") or [])
    region = list(pack.get("region_factories") or [])
    work = pack.get("work") or {}
    auto = pack.get("auto") or {}
    province = pack.get("province")

    base = analyze_factories(factories, work, auto, province=province)
    work_fid = str(work.get("factory_id") or work.get("current_factory_id") or "")

    owned_numbered = [
        enrich_owned(f, index=i, cfg=cfg, work_factory_id=work_fid or None)
        for i, f in enumerate(factories, start=1)
    ]
    region_numbered = [
        enrich_region(f, index=i, cfg=cfg, work_factory_id=work_fid or None)
        for i, f in enumerate(region, start=1)
    ]

    primary = None
    if cfg.primary_factory_id:
        primary = next((w for w in owned_numbered if w.get("factory_id") == cfg.primary_factory_id), None)
    if not primary and owned_numbered:
        primary = owned_numbered[0]

    preferred = None
    if cfg.preferred_factory_id:
        preferred = next(
            (w for w in owned_numbered + region_numbered if w.get("factory_id") == cfg.preferred_factory_id),
            None,
        )

    tips = list(base.get("tips") or [])
    if cfg.work_mode == "fixed" and not cfg.preferred_factory_id:
        tips.insert(0, "Sabit mod — 🎯 ile fabrika seç veya /setfabric uuid")
    if owned_numbered and not cfg.primary_factory_id:
        tips.append("Ana fabrika seçilmedi — 🎯N ile işaretle")

    return {
        **base,
        "owned_numbered": owned_numbered,
        "region_numbered": region_numbered,
        "owned_ids": [w["factory_id"] for w in owned_numbered if w.get("factory_id")],
        "region_ids": [w["factory_id"] for w in region_numbered if w.get("factory_id")],
        "primary": primary,
        "primary_index": primary.get("index") if primary else None,
        "preferred": preferred,
        "work_mode": cfg.work_mode,
        "work_mode_label": WORK_MODE_LABELS.get(cfg.work_mode, cfg.work_mode),
        "allow_auto_build": cfg.allow_auto_build,
        "preferred_factory_id": cfg.preferred_factory_id,
        "primary_factory_id": cfg.primary_factory_id,
        "default_salary_rate": cfg.default_salary_rate,
        "default_build_name": cfg.default_build_name,
        "province": province,
        "diamonds": (pack.get("profile") or {}).get("diamonds"),
        "tips": tips[:5],
        "can_work": base.get("work_ready") or base.get("working"),
    }


def format_factory_board_html(
    pack: dict,
    analysis: dict | None = None,
    cfg: AccountConfig | None = None,
) -> str:
    cfg = cfg or AccountConfig("x")
    if analysis is None:
        analysis = analyze_factory_board_enriched(pack, cfg)
    elif "owned_numbered" not in analysis:
        analysis = analyze_factory_board_enriched(pack, cfg)

    lines = [
        "<b>🏭 Fabrika merkezi</b>",
        f"Mod: <b>{html.escape(analysis.get('work_mode_label') or '?')}</b>"
        + (
            f" → <code>{html.escape(str(analysis.get('preferred_factory_id'))[:36])}</code>"
            if analysis.get("preferred_factory_id")
            else ""
        ),
        f"Sahip: {analysis.get('owned', 0)} · İşçi: {analysis.get('total_workers', 0)}",
    ]

    if analysis.get("working"):
        wf = analysis.get("work_factory_id") or "?"
        lines.append(f"✅ Çalışıyor: <code>{html.escape(str(wf))}</code>")
    elif analysis.get("work_ready"):
        lines.append("✅ Work hazır — 🗡️ Çalış veya farm başlat")
    else:
        lines.append(f"⏳ Work: {format_ms(analysis.get('work_wait_ms'))}")

    owned = analysis.get("owned_numbered") or []
    if owned:
        lines.append(f"\n<b>Senin fabrikaların</b> ({len(owned)})")
        for w in owned[:6]:
            idx = w.get("index", 0)
            marks = []
            if w.get("is_primary"):
                marks.append("🎯")
            if w.get("is_preferred"):
                marks.append("📌")
            if w.get("is_working_here"):
                marks.append("⚙️")
            mark = " ".join(marks) + " " if marks else ""
            name = html.escape(str(w.get("display_name")))
            lvl = w.get("level_int", "?")
            closed = "🔒 kapalı" if w.get("is_closed") else "🟢 açık"
            prov = html.escape(str(w.get("province_label")))
            bal = w.get("balance_int", 0)
            sal = w.get("salary_pct")
            sal_txt = f" · maaş %{sal}" if sal is not None else ""
            lines.append(
                f"\n<b>{idx}.</b> {mark}<b>{name}</b> lv{lvl} · {w.get('type_label', '?')}{sal_txt}"
            )
            lines.append(f"   {closed} · 💰 {bal:,}₺ · 👷 {w.get('workers_int', 0)} · 📍 {prov}")
            fid = w.get("factory_id")
            if fid:
                lines.append(f"   <code>{html.escape(fid)}</code>")
    else:
        lines.append("\n<i>Henüz fabrikan yok — 🏗️ Kur veya bölgeden katıl</i>")

    region = analysis.get("region_numbered") or []
    if region:
        lines.append(f"\n<b>📍 Bölgedeki fabrikalar</b> ({len(region)})")
        for w in region[:6]:
            ridx = w.get("index", 0)
            name = html.escape(str(w.get("display_name")))
            owner = html.escape(str(w.get("owner_label")))
            pin = " 📌" if w.get("is_preferred") else ""
            work = " ⚙️" if w.get("is_working_here") else ""
            lvl = w.get("level_int", "?")
            lines.append(
                f"<b>R{ridx}.</b> {name} — {owner}{pin}{work}\n"
                f"   {w.get('type_label', '?')} lv{lvl}"
            )

    p = analysis.get("primary")
    if p:
        lines.append(
            f"\n<b>🎯 Ana fabrika: #{p.get('index')} {html.escape(str(p.get('display_name')))}</b>"
        )
    lines.append(
        f"<i>DB: primary={html.escape(str(cfg.primary_factory_id or '—')[:8])} "
        f"· build={'evet' if cfg.allow_auto_build else 'hayır'}</i>"
    )
    lines.append("<i>🎯N ana · 📌N sabit · 🗡️ çalış · R katıl · 🔒 kapat · 💰 çek</i>")

    for tip in analysis.get("tips", [])[:3]:
        lines.append(f"\n💡 {html.escape(str(tip))}")

    return "\n".join(lines)


def format_factory_action_html(result: dict) -> str:
    action = html.escape(str(result.get("action") or "?"))
    if result.get("ok"):
        msg = html.escape(str(result.get("message") or "Tamam")[:300])
        extra = ""
        earned = result.get("earned")
        if isinstance(earned, dict) and earned:
            parts = [f"{k}: {v}" for k, v in earned.items() if v]
            if parts:
                extra = "\n" + html.escape(", ".join(parts))
        fid = result.get("factory_id")
        fid_line = f"\n🏭 <code>{html.escape(str(fid))}</code>" if fid else ""
        return f"<b>🏭 {action}</b> ✅\n{msg}{extra}{fid_line}"
    err = html.escape(str(result.get("error") or result)[:300])
    return f"<b>🏭 {action}</b> ❌\n{err}"


def factory_board_inline_markup(analysis: dict) -> "InlineKeyboardMarkup":
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    from .telegram_ui import back_home_button

    owned = (analysis or {}).get("owned_numbered") or []
    region = (analysis or {}).get("region_numbered") or []
    rows: list[list] = []

    pick_row: list = []
    fixed_row: list = []
    for w in owned[:4]:
        i = int(w.get("index") or 0)
        if not i:
            continue
        star = "⭐" if w.get("is_primary") else ""
        pick_row.append(InlineKeyboardButton(f"🎯{i}{star}", callback_data=f"fab:primary:{i}"))
        pin = "📌" if w.get("is_preferred") else ""
        fixed_row.append(InlineKeyboardButton(f"📌{i}{pin}", callback_data=f"fab:fixed:{i}"))
    if pick_row:
        rows.append(pick_row)
        rows.append(fixed_row)

    act_row: list = []
    for w in owned[:3]:
        i = int(w.get("index") or 0)
        if i:
            act_row.append(InlineKeyboardButton(f"💰{i}", callback_data=f"fab:withdraw:{i}"))
            act_row.append(InlineKeyboardButton(f"⬆️{i}", callback_data=f"fab:level:{i}"))
            act_row.append(InlineKeyboardButton(f"🔒{i}", callback_data=f"fab:close:{i}"))
    if act_row:
        rows.append(act_row[:6])

    join_row: list = []
    for w in region[:4]:
        i = int(w.get("index") or 0)
        if i:
            join_row.append(InlineKeyboardButton(f"R{i}➕", callback_data=f"fab:join:r:{i}"))
    if join_row:
        rows.append(join_row)

    mode = str((analysis or {}).get("work_mode") or "own")
    rows.append(
        [
            InlineKeyboardButton(
                "Kendi" + (" ✓" if mode == "own" else ""),
                callback_data="fab:mode:own",
            ),
            InlineKeyboardButton(
                "Yabancı" + (" ✓" if mode == "foreign" else ""),
                callback_data="fab:mode:foreign",
            ),
            InlineKeyboardButton(
                "Oto" + (" ✓" if mode == "auto" else ""),
                callback_data="fab:mode:auto",
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🗡️ Çalış", callback_data="fab:work"),
            InlineKeyboardButton("🚪 Ayrıl", callback_data="fab:leave"),
            InlineKeyboardButton("🏗️ Kur", callback_data="fab:build"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🔄 Yenile", callback_data="action:myfactory"),
            back_home_button(),
        ]
    )
    return InlineKeyboardMarkup(rows)


def factory_board_callback_rows(analysis: dict) -> list[list[tuple[str, str]]]:
    owned = (analysis or {}).get("owned_numbered") or []
    region = (analysis or {}).get("region_numbered") or []
    rows: list[list[tuple[str, str]]] = []

    pick: list[tuple[str, str]] = []
    for w in owned[:4]:
        i = int(w.get("index") or 0)
        if i:
            star = "⭐" if w.get("is_primary") else ""
            pick.append((f"🎯{i}{star}", f"fab:primary:{i}"))
    if pick:
        rows.append(pick)

    join: list[tuple[str, str]] = []
    for w in region[:4]:
        i = int(w.get("index") or 0)
        if i:
            join.append((f"R{i}➕", f"fab:join:r:{i}"))
    if join:
        rows.append(join)

    mode = str((analysis or {}).get("work_mode") or "own")
    rows.append(
        [
            ("Kendi" + (" ✓" if mode == "own" else ""), "fab:mode:own"),
            ("Yabancı" + (" ✓" if mode == "foreign" else ""), "fab:mode:foreign"),
            ("🗡️ Çalış", "fab:work"),
        ]
    )
    rows.append([("🔄 Yenile", "action:myfactory"), ("🏠 Ana Sayfa", "dash:home")])
    return rows


def resolve_factory_index(
    analysis: dict,
    *,
    list_kind: str,
    index: int,
) -> str | None:
    if list_kind == "owned":
        items = analysis.get("owned_numbered") or []
    else:
        items = analysis.get("region_numbered") or []
    pick = next((w for w in items if int(w.get("index") or 0) == index), None)
    return str(pick.get("factory_id") or "") if pick else None
