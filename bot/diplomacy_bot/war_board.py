"""Savaş panosu — zenginleştirme ve format yardımcıları."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from .account_config import AccountConfig


def _parse_power(val: Any) -> int:
    try:
        return int(str(val or "0").replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _normalize_country(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip()).upper()


def detect_player_side(war: dict, player_country: str | None) -> str | None:
    """Oyuncu ülkesi saldıran/savunan tarafta mı."""
    if war.get("my_side"):
        return str(war["my_side"])
    if war.get("player_side"):
        return str(war["player_side"])
    c = _normalize_country(player_country)
    if not c:
        return None
    atk = _normalize_country(war.get("attacker_name") or war.get("attacker_country"))
    defn = _normalize_country(war.get("defender_name") or war.get("defender_country"))
    # TÜRKELİ (İSFAHAN) → TÜRKELİ eşleşmesi
    atk_short = atk.split("(")[0].strip() if atk else ""
    def_short = defn.split("(")[0].strip() if defn else ""
    for side, full, short in (
        ("attacker", atk, atk_short),
        ("defender", defn, def_short),
    ):
        if c and (c in full or full in c or c in short or short in c):
            return side
    return None


def time_left_label(ends_at: str | None) -> str:
    if not ends_at:
        return "?"
    try:
        end = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
        delta = end - datetime.now(timezone.utc)
        sec = int(delta.total_seconds())
        if sec <= 0:
            return "süresi doldu"
        h, rem = divmod(sec, 3600)
        m = rem // 60
        if h >= 24:
            d, h = divmod(h, 24)
            return f"{d}g {h}s"
        if h:
            return f"{h}s {m}dk"
        return f"{m}dk"
    except Exception:
        return "?"


def power_bar(attacker: int, defender: int, width: int = 12) -> tuple[str, int, int]:
    total = attacker + defender
    if total <= 0:
        return "░" * width, 50, 50
    atk_pct = int(attacker * 100 / total)
    filled = round(width * attacker / total)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled), atk_pct, 100 - atk_pct


def enrich_war(
    war: dict,
    *,
    index: int,
    player_country: str | None,
    target_war_id: str | None,
) -> dict[str, Any]:
    atk = _parse_power(war.get("attacker_power"))
    defn = _parse_power(war.get("defender_power"))
    bar, atk_pct, def_pct = power_bar(atk, defn)
    side = detect_player_side(war, player_country)
    wid = str(war.get("id") or "")
    title = war.get("war_name") or war.get("name")
    if not title:
        wtype = war.get("war_type") or "savaş"
        prov_a = war.get("attacker_province") or "?"
        prov_d = war.get("defender_province") or "?"
        title = f"{wtype.title()} — {prov_a}/{prov_d}"
    goals = war.get("war_goals") or []
    goal_txt = ", ".join(str(g) for g in goals[:2]) if goals else ""
    return {
        **war,
        "index": index,
        "display_title": str(title),
        "attacker_power_int": atk,
        "defender_power_int": defn,
        "power_bar": bar,
        "attacker_pct": atk_pct,
        "defender_pct": def_pct,
        "my_side": side,
        "is_target": bool(target_war_id and wid == target_war_id),
        "is_player_war": side is not None,
        "time_left": time_left_label(war.get("ends_at")),
        "goal_label": goal_txt,
        "short_id": wid[:8] if wid else "?",
    }


def analyze_wars_enriched(
    data: dict,
    cfg: AccountConfig | None = None,
    *,
    player_country: str | None = None,
) -> dict[str, Any]:
    from .feature_analysis import analyze_wars

    base = analyze_wars(data, cfg)
    cfg = cfg or AccountConfig("x")
    active = list(base.get("active") or [])

    def sort_key(w: dict) -> tuple:
        side = detect_player_side(w, player_country)
        involved = 0 if side else 1
        ends = w.get("ends_at") or "9999"
        return (involved, ends)

    active.sort(key=sort_key)
    numbered = [
        enrich_war(
            w,
            index=i,
            player_country=player_country,
            target_war_id=cfg.target_war_id,
        )
        for i, w in enumerate(active, start=1)
    ]
    target = None
    if cfg.target_war_id:
        target = next((w for w in numbered if w.get("is_target")), None)
    if not target and numbered:
        target = numbered[0]

    side = cfg.contribute_side
    if side == "auto" and target:
        side = target.get("my_side") or "attacker"

    player_wars = [w for w in numbered if w.get("is_player_war")]
    return {
        **base,
        "active": active,
        "numbered": numbered,
        "target": target,
        "target_index": target.get("index") if target else None,
        "suggested_side": side,
        "player_country": player_country,
        "player_war_count": len(player_wars),
    }


def format_war_board_html(
    data: dict,
    analysis: dict | None = None,
    cfg: AccountConfig | None = None,
) -> str:
    cfg = cfg or AccountConfig("x")
    if analysis is None:
        analysis = analyze_wars_enriched(data, cfg)
    elif "numbered" not in analysis:
        analysis = analyze_wars_enriched(data, cfg, player_country=analysis.get("player_country"))

    lines = [
        f"<b>⚔️ Savaş panosu</b> — {analysis.get('war_count', 0)} aktif",
    ]
    pc = analysis.get("player_country")
    if pc:
        lines.append(f"Ülken: <b>{html.escape(str(pc))}</b> · senin savaşların: {analysis.get('player_war_count', 0)}")

    numbered = analysis.get("numbered") or []
    if not numbered:
        lines.append("\nAktif savaş yok.")
        lines.append("<i>Ülke savaşı başlayınca burada görünür</i>")
        return "\n".join(lines)

    for w in numbered[:8]:
        idx = w.get("index", 0)
        mark = "🎯 " if w.get("is_target") else ""
        pin = " ⭐" if w.get("is_player_war") else ""
        title = html.escape(str(w.get("display_title") or "Savaş"))
        status = html.escape(str(w.get("status", "?")))
        atk = html.escape(str(w.get("attacker_name") or w.get("attacker_province") or "?"))
        defn = html.escape(str(w.get("defender_name") or w.get("defender_province") or "?"))
        atk_p = w.get("attacker_power_int", 0)
        def_p = w.get("defender_power_int", 0)
        bar = w.get("power_bar", "")
        atk_pct = w.get("attacker_pct", 50)
        def_pct = w.get("defender_pct", 50)
        time_l = html.escape(str(w.get("time_left") or "?"))
        side = w.get("my_side")
        side_txt = ""
        if side:
            side_txt = f" · <b>Sen: {'saldırgan' if side == 'attacker' else 'savunucu'}</b>"

        lines.append(f"\n<b>{idx}.</b> {mark}<b>{title}</b> [{status}]{pin}")
        lines.append(f"   ⚔️ {atk} vs 🛡️ {defn}")
        lines.append(f"   <code>{bar}</code> {atk_pct}% — {def_pct}%")
        lines.append(f"   💪 {atk_p:,} vs {def_p:,} · ⏱ {time_l}{side_txt}")
        prov = []
        if w.get("attacker_province"):
            prov.append(f"📍 {html.escape(str(w['attacker_province']))}")
        if w.get("defender_province"):
            prov.append(f"→ {html.escape(str(w['defender_province']))}")
        if prov:
            lines.append(f"   {' '.join(prov)}")
        if w.get("goal_label"):
            lines.append(f"   🎯 Hedef: {html.escape(str(w['goal_label']))}")
        if w.get("is_conquest"):
            lines.append("   🏴 Fetih savaşı")
        wid = w.get("id")
        if wid:
            lines.append(f"   <code>{html.escape(str(wid))}</code>")

    t = analysis.get("target")
    if t:
        ti = t.get("index", "?")
        tname = html.escape(str(t.get("display_title") or t.get("war_name") or "?"))
        side = html.escape(str(analysis.get("suggested_side") or "attacker"))
        side_tr = "saldırgan" if side == "attacker" else "savunucu"
        lines.append(f"\n<b>🎯 Hedef: #{ti} {tname}</b>")
        lines.append(f"Katkı tarafı: <b>{side_tr}</b> (<code>{side}</code>)")
        lines.append("<i>Altta 🎯N = hedef seç · 🗡️N = o savaşa katkı</i>")
    elif analysis.get("can_contribute"):
        lines.append("\n<i>🗡️ Katkı ver — hedef savaşa asker gönder</i>")
    else:
        lines.append("\n<i>⚙️ Savaş için rol: war veya hybrid + savaş açık</i>")

    return "\n".join(lines)


def war_board_inline_markup(analysis: dict, *, attacks_enabled: bool = True) -> "InlineKeyboardMarkup":
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    from .telegram_ui import back_home_button

    numbered = (analysis or {}).get("numbered") or []
    rows: list[list[InlineKeyboardButton]] = []

    pick_row: list[InlineKeyboardButton] = []
    contrib_row: list[InlineKeyboardButton] = []
    for w in numbered[:5]:
        i = int(w.get("index") or 0)
        if not i:
            continue
        star = "⭐" if w.get("is_target") else ""
        pick_row.append(
            InlineKeyboardButton(f"🎯{i}{star}", callback_data=f"war:pick:{i}")
        )
        contrib_row.append(
            InlineKeyboardButton(f"🗡️{i}", callback_data=f"war:contrib:{i}")
        )
    if pick_row and attacks_enabled:
        rows.append(pick_row)
        rows.append(contrib_row)

    if attacks_enabled:
        side = str((analysis or {}).get("suggested_side") or "attacker")
        rows.append(
            [
                InlineKeyboardButton(
                    "⚔️ Saldırgan" + (" ✓" if side == "attacker" else ""),
                    callback_data="war:side:attacker",
                ),
                InlineKeyboardButton(
                    "🛡️ Savunucu" + (" ✓" if side == "defender" else ""),
                    callback_data="war:side:defender",
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton("🗡️ Hedefe katkı", callback_data="action:warcontrib"),
                InlineKeyboardButton("🔄 Yenile", callback_data="action:wars"),
            ]
        )
    else:
        rows.append([InlineKeyboardButton("🔄 Yenile", callback_data="action:wars")])
    rows.append([back_home_button()])
    return InlineKeyboardMarkup(rows)


def war_board_callback_rows(analysis: dict) -> list[list[tuple[str, str]]]:
    """AgentResult / intent_router için tuple buton satırları."""
    numbered = (analysis or {}).get("numbered") or []
    rows: list[list[tuple[str, str]]] = []
    pick: list[tuple[str, str]] = []
    contrib: list[tuple[str, str]] = []
    for w in numbered[:4]:
        i = int(w.get("index") or 0)
        if not i:
            continue
        star = "⭐" if w.get("is_target") else ""
        pick.append((f"🎯{i}{star}", f"war:pick:{i}"))
        contrib.append((f"🗡️{i}", f"war:contrib:{i}"))
    if pick:
        rows.append(pick)
        rows.append(contrib)
    side = str((analysis or {}).get("suggested_side") or "attacker")
    rows.append(
        [
            ("⚔️ Saldırgan" + (" ✓" if side == "attacker" else ""), "war:side:attacker"),
            ("🛡️ Savunucu" + (" ✓" if side == "defender" else ""), "war:side:defender"),
        ]
    )
    rows.append([("🗡️ Hedefe katkı", "action:warcontrib"), ("🔄 Yenile", "action:wars")])
    rows.append([("🏠 Ana Sayfa", "dash:home")])
    return rows
