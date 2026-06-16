"""Stat merkezi — okunaklı isimler (30+ UX), otomatik altın yükseltme."""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

from .account_config import AccountConfig, DEFAULT_STAT_PRIORITY
from .modules.stats import pending_seconds_remaining, resolve_active_priority, resolve_priority, skill_is_pending

# Ekranda ve butonda: Türkçe isim (numara yok)
SKILL_NAMES_TR: dict[str, str] = {
    "kisla": "Kışla",
    "bilim_insani": "Bilim insanı",
    "savas_teknikleri": "Savaş teknikleri",
    "ekonomi": "Ekonomi",
    "vergi_uzmani": "Vergi uzmanı",
    "guc": "Güç",
    "güç": "Güç",
    "ticaret": "Ticaret",
    "uretim": "Üretim",
    "arastirma": "Araştırma",
}

SKILL_LABELS_TR: dict[str, str] = {k: f"🪖 {v}" if k == "kisla" else f"🔬 {v}" if k == "bilim_insani" else f"⚔️ {v}" if k == "savas_teknikleri" else f"📌 {v}" for k, v in SKILL_NAMES_TR.items()}
SKILL_LABELS_TR.update({
    "ekonomi": "💰 Ekonomi",
    "vergi_uzmani": "📊 Vergi uzmanı",
})

# Konuşma / komut eşlemesi
SKILL_ALIASES: dict[str, list[str]] = {
    "kisla": ["kisla", "kışla", "kis", "barak", "kisla becerisi"],
    "bilim_insani": ["bilim", "bilim insanı", "bilim insani", "biliminsanı", "bilim insani"],
    "savas_teknikleri": ["savaş", "savas", "savaş teknikleri", "savas teknikleri", "savaş teknik", "savas teknik"],
    "ekonomi": ["ekonomi"],
    "vergi_uzmani": ["vergi", "vergi uzmanı", "vergi uzmani"],
}


def _norm_token(s: str) -> str:
    t = unicodedata.normalize("NFKD", (s or "").strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t)


def skill_short_name(key: str) -> str:
    k = (key or "").strip()
    return SKILL_NAMES_TR.get(k, SKILL_NAMES_TR.get(k.lower(), k.replace("_", " ")))


def skill_label(key: str) -> str:
    k = (key or "").strip()
    if k in SKILL_LABELS_TR:
        return SKILL_LABELS_TR[k]
    return SKILL_LABELS_TR.get(k.lower(), f"📌 {skill_short_name(k)}")


def skill_prio_button_label(key: str, *, is_primary: bool) -> str:
    name = skill_short_name(key)
    return f"✓ {name}" if is_primary else name


def _skill_level(val: Any) -> int:
    if isinstance(val, dict):
        return int(val.get("level") or val.get("lvl") or 0)
    try:
        return int(val or 0)
    except (ValueError, TypeError):
        return 0


def _base_active_keys(active_raw: dict) -> list[str]:
    return [k for k in active_raw if isinstance(k, str) and "_pending" not in k]


def resolve_active_skill_key(analysis: dict, token: str) -> str | None:
    """Türkçe isim, API anahtarı veya eski #numara → skill key."""
    raw = (token or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return resolve_active_skill_index(analysis, int(raw))
    keys = list(analysis.get("active_skill_keys") or [])
    key_set = set(keys)
    if raw in key_set:
        return raw
    norm = _norm_token(raw)
    for k in keys:
        if _norm_token(k) == norm or _norm_token(skill_short_name(k)) == norm:
            return k
    for key, aliases in SKILL_ALIASES.items():
        if key not in key_set:
            continue
        if _norm_token(key) == norm:
            return key
        for alias in aliases:
            if norm == _norm_token(alias) or norm in _norm_token(alias) or _norm_token(alias) in norm:
                return key
    return None


def resolve_skill_keys_list(tokens: list[str], analysis: dict | None = None) -> list[str]:
    """Virgülle ayrılmış isim listesi → API anahtarları."""
    out: list[str] = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        if analysis:
            k = resolve_active_skill_key(analysis, t)
            if k and k not in out:
                out.append(k)
                continue
        # ham anahtar (setstat kisla,bilim_insani)
        norm = _norm_token(t)
        for key, aliases in SKILL_ALIASES.items():
            if norm == _norm_token(key) or any(norm == _norm_token(a) for a in aliases):
                if key not in out:
                    out.append(key)
                break
        else:
            if t not in out:
                out.append(t)
    return out


# Varsayılan skill upgrade cooldown (~27 sn) — API süre vermezse tahmin
DEFAULT_SKILL_COOLDOWN_SEC = 27


def _format_pending_wait(sec: int | None) -> str:
    if sec is not None and sec > 0:
        return f"{sec} sn kaldı"
    if sec == 0:
        return "bitiyor — Yenile"
    return f"~{DEFAULT_SKILL_COOLDOWN_SEC} sn (tahmini)"


def format_active_skill_line(s: dict) -> str:
    """Tek aktif stat satırı — durum rozeti ile."""
    name = html.escape(str(s.get("name") or skill_short_name(str(s.get("key")))))
    lvl = int(s.get("level") or 0)
    if s.get("is_pending") and s.get("pending_level"):
        wait = _format_pending_wait(s.get("pending_seconds_remaining"))
        return f"⏳ {name} — {lvl} → {s.get('pending_level')} · {wait}"
    badge = "▶" if s.get("is_primary") else "•"
    return f"{badge} {name} — seviye {lvl}"


def compute_stat_automation_status(analysis: dict) -> dict[str, Any]:
    """Otomasyon özeti — kullanıcı «ne oluyor?» sorusuna tek satır."""
    active = analysis.get("active_numbered") or []
    primary_name = analysis.get("primary_name")
    primary_key = analysis.get("primary_active")
    auto_on = bool(analysis.get("stat_auto_enabled", True))
    pending = [s for s in active if s.get("is_pending")]

    if pending:
        p = pending[0]
        pname = html.escape(str(p.get("name") or skill_short_name(str(p.get("key")))))
        plvl = p.get("pending_level")
        wait = _format_pending_wait(p.get("pending_seconds_remaining"))
        primary_pending = primary_key and any(
            str(s.get("key")) == primary_key and s.get("is_pending") for s in active
        )
        if auto_on and primary_name and not primary_pending:
            pn = html.escape(str(primary_name))
            summary = f"⏳ {pname} bitince → <b>{pn}</b> sıraya girer ({wait})"
        else:
            summary = f"⏳ {pname} → {plvl} yükseliyor ({wait})"
        return {"kind": "pending", "summary": summary, "pending_key": p.get("key")}

    if not auto_on:
        return {
            "kind": "manual",
            "summary": "⏸ Otomatik kapalı — «Şimdi uygula» veya elmas",
        }

    if primary_name:
        pn = html.escape(str(primary_name))
        return {
            "kind": "ready",
            "summary": f"▶ <b>{pn}</b> sıradaki — kuyruk altınla yükseltir",
        }

    return {"kind": "idle", "summary": "✓ Yükseltme beklemesi yok"}


def enrich_active_skill(
    key: str,
    level: Any,
    *,
    index: int,
    priority_rank: int | None,
    is_primary: bool,
    active_raw: dict | None = None,
) -> dict[str, Any]:
    pending_lvl = None
    pending_sec = None
    if active_raw:
        pending_lvl = active_raw.get(f"{key}_pending")
        if skill_is_pending(active_raw, key):
            pending_sec = pending_seconds_remaining(active_raw, key)
    return {
        "key": key,
        "index": index,
        "name": skill_short_name(key),
        "label": skill_label(key),
        "level": _skill_level(level),
        "pending_level": int(pending_lvl) if pending_lvl else None,
        "pending_seconds_remaining": pending_sec,
        "is_pending": skill_is_pending(active_raw or {}, key),
        "kind": "active",
        "priority_rank": priority_rank,
        "is_primary": is_primary,
    }


def enrich_passive_skill(
    key: str,
    val: Any,
    *,
    index: int,
    priority_rank: int | None,
    is_next: bool,
    available: int,
) -> dict[str, Any]:
    return {
        "key": key,
        "index": index,
        "name": skill_short_name(key),
        "label": skill_label(key),
        "level": _skill_level(val),
        "priority_rank": priority_rank,
        "is_next": is_next and available > 0,
        "kind": "passive",
    }


def analyze_stat_board_enriched(
    pack: dict,
    cfg: AccountConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or AccountConfig("x")
    passive_data = pack.get("passive_data") or {}
    passive_skills = passive_data.get("passive_skills") or {}
    if not isinstance(passive_skills, dict):
        passive_skills = {}

    available = int(passive_data.get("available_points") or pack.get("profile_pts") or 0)
    player_class = pack.get("player_class")
    balance = int(pack.get("balance") or 0)
    diamonds = int(pack.get("diamonds") or 0)

    active_raw = pack.get("active_skills") or {}
    if not isinstance(active_raw, dict):
        active_raw = {}

    base_keys = _base_active_keys(active_raw)
    active_priority = resolve_active_priority(cfg, base_keys)
    active_prio_rank = {k: i + 1 for i, k in enumerate(active_priority)}
    primary_active = active_priority[0] if active_priority else None

    active_numbered = [
        enrich_active_skill(
            k,
            active_raw[k],
            index=i,
            priority_rank=active_prio_rank.get(k),
            is_primary=k == primary_active,
            active_raw=active_raw,
        )
        for i, k in enumerate(active_priority, start=1)
        if k in active_raw and "_pending" not in k
    ]

    passive_keys = list(passive_skills.keys())
    passive_priority = resolve_priority(cfg, player_class, passive_keys)
    next_passive = passive_priority[0] if passive_priority and available > 0 else None

    passive_numbered: list[dict[str, Any]] = []
    seen: list[str] = []
    for k in passive_priority + passive_keys:
        if k in passive_skills and k not in seen:
            seen.append(k)
    for i, k in enumerate(seen, start=1):
        passive_numbered.append(
            enrich_passive_skill(
                k,
                passive_skills.get(k, 0),
                index=i,
                priority_rank=None,
                is_next=k == next_passive,
                available=available,
            )
        )

    auto_on = bool(getattr(cfg, "stat_auto_enabled", True))
    auto_status = compute_stat_automation_status(
        {
            "active_numbered": active_numbered,
            "primary_name": skill_short_name(primary_active) if primary_active else None,
            "primary_active": primary_active,
            "stat_auto_enabled": auto_on,
        }
    )
    from .stat_queue import preview_stat_queue

    queue_status = preview_stat_queue(active_raw, cfg, cfg.account_name)
    tips: list[str] = []
    if auto_on:
        from .stat_queue import STAT_QUEUE_INTERVAL_SEC

        tips.append(
            f"Kuyruk her {STAT_QUEUE_INTERVAL_SEC} sn kontrol edilir; farm ile de tetiklenir."
        )
    else:
        tips.append("Otomatik kapalı — «Şimdi uygula» veya elmas kullan.")

    return {
        "available": available,
        "balance": balance,
        "diamonds": diamonds,
        "stat_auto_enabled": auto_on,
        "auto_status": auto_status,
        "queue_status": queue_status,
        "active_numbered": active_numbered,
        "passive_numbered": passive_numbered,
        "active_skill_keys": [s["key"] for s in active_numbered],
        "passive_skill_keys": [s["key"] for s in passive_numbered],
        "skill_keys": [s["key"] for s in passive_numbered],
        "active_priority": active_priority[:6],
        "primary_active": primary_active,
        "primary_name": skill_short_name(primary_active) if primary_active else None,
        "next_passive": next_passive,
        "next_skill": next_passive,
        "can_spend": available > 0,
        "can_upgrade": bool(active_numbered),
        "player_class": player_class,
        "tips": tips[:2],
    }


def format_stat_status_combined(
    auto_status: dict,
    queue_status: dict | None,
    *,
    auto_on: bool,
) -> str:
    """Durum + Kuyruk — tek satır, tekrarsız."""
    ast = auto_status.get("summary") or "—"
    if not auto_on:
        return ast
    qs = queue_status or {}
    qsum = str(qs.get("summary") or "").strip()
    if not qsum or qs.get("kind") == "disabled":
        return ast
    kind = auto_status.get("kind")
    qesc = html.escape(qsum)
    if kind == "pending":
        return f"⏱ {qesc}"
    if kind == "ready":
        return f"{ast} · <i>{qesc}</i>"
    if kind == "manual":
        return ast
    return qesc


def format_stat_board_html(
    pack: dict,
    analysis: dict | None = None,
    cfg: AccountConfig | None = None,
) -> str:
    cfg = cfg or AccountConfig("x")
    if analysis is None:
        analysis = analyze_stat_board_enriched(pack, cfg)

    auto_on = analysis.get("stat_auto_enabled", cfg.stat_auto_enabled)
    auto_status = analysis.get("auto_status") or compute_stat_automation_status(analysis)
    queue_status = analysis.get("queue_status") or {}
    status_line = format_stat_status_combined(auto_status, queue_status, auto_on=auto_on)
    lines = [
        "<b>Statlar</b>",
        f"Otomatik: <b>{'Açık' if auto_on else 'Kapalı'}</b>"
        + (" — kuyruk + farm ile altınla yükselir" if auto_on else ""),
        f"💰 {int(analysis.get('balance') or 0):,} ₺  ·  💎 {int(analysis.get('diamonds') or 0):,}",
        f"\n<b>Durum:</b> {status_line}",
    ]

    primary_name = analysis.get("primary_name")
    if primary_name:
        lines.append(f"<b>Önce yükseltilen:</b> {html.escape(str(primary_name))}")

    active = analysis.get("active_numbered") or []
    if active:
        lines.append("")
        for s in active:
            lines.append(format_active_skill_line(s))
    else:
        lines.append("\n<i>Stat bilgisi alınamadı.</i>")

    pts = int(analysis.get("available") or 0)
    if pts > 0:
        lines.append(f"\nPasif bonus: <b>{pts}</b> puan" + (" — otomatik harcanır" if auto_on else ""))

    passive = analysis.get("passive_numbered") or []
    for s in passive[:3]:
        name = html.escape(str(s.get("name") or ""))
        lines.append(f"  Pasif · {name} — seviye {s.get('level', 0)}")

    lines.append("\n<i>Öncelik: alttaki isim · elmas: «Elmas ile» · sayaç: «Yenile»</i>")
    if analysis.get("tips"):
        lines.append(f"💡 {html.escape(str(analysis['tips'][0]))}")

    return "\n".join(lines)


def format_stat_auto_result_html(result: dict, analysis: dict | None = None) -> str:
    lines = ["<b>Son işlem — stat otomasyonu</b>"]
    ok_any = False
    for u in result.get("upgrades") or []:
        if u.get("ok"):
            ok_any = True
            name = html.escape(skill_short_name(str(u.get("skill") or "?")))
            lvl = u.get("new_level")
            extra = f" → seviye {lvl}" if lvl else ""
            sec = None
            if u.get("pending_at"):
                from .modules.stats import pending_seconds_remaining

                sec = pending_seconds_remaining(
                    {f"{u.get('skill')}_pending_at": u.get("pending_at")},
                    str(u.get("skill") or ""),
                )
            if sec is not None and sec > 0:
                extra += f" · {sec} sn ⏳"
            elif u.get("pending_at"):
                extra += " ⏳"
            lines.append(f"✅ {name} yükseltildi (altın){extra}")
        elif u.get("error"):
            name = html.escape(skill_short_name(str(u.get("skill") or "?")))
            err = html.escape(str(u.get("error"))[:120])
            lines.append(f"⏭ {name}: {err}")
    for p in result.get("passive") or []:
        if p.get("ok"):
            ok_any = True
            name = html.escape(skill_short_name(str(p.get("skill") or "?")))
            lines.append(f"✅ Pasif puan → {name}")
    if not ok_any:
        idle = result.get("idle_summary")
        if not idle and analysis:
            st = compute_stat_automation_status(analysis)
            idle = st.get("summary")
        if idle:
            lines.append(f"ℹ️ {idle}")
        else:
            lines.append(
                f"ℹ️ {html.escape(str(result.get('error') or 'Şu an yapılacak bir şey yok')[:200])}"
            )
    return "\n".join(lines)


def format_stat_spend_result_html(result: dict, analysis: dict | None = None) -> str:
    if result.get("action") == "auto":
        return format_stat_auto_result_html(
            result, analysis or result.get("analysis")
        )
    if result.get("action") == "upgrade" and result.get("ok"):
        name = html.escape(skill_short_name(str(result.get("skill") or "?")))
        cur = "altın" if result.get("currency") == "gold" else "elmas"
        lvl = result.get("new_level")
        extra = f" → seviye <b>{lvl}</b>" if lvl is not None else ""
        if result.get("pending_at"):
            extra += " ⏳"
        return f"<b>Yükseltildi</b> ✅\n{name} ({cur}){extra}"
    if result.get("ok"):
        name = html.escape(skill_short_name(str(result.get("skill") or "?")))
        return f"<b>Pasif harcandı</b> ✅\n→ {name}"
    if result.get("spent_list"):
        from .feature_reports import format_stat_spend_html

        return format_stat_spend_html(result["spent_list"])
    err = html.escape(str(result.get("error") or "?")[:250])
    return f"<b>İşlem başarısız</b> ❌\n{err}"


def stat_board_inline_markup(analysis: dict) -> "InlineKeyboardMarkup":
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    from .telegram_ui import back_home_button

    active = (analysis or {}).get("active_numbered") or []
    available = int((analysis or {}).get("available") or 0)
    auto_on = bool((analysis or {}).get("stat_auto_enabled", True))
    has_pending = any(s.get("is_pending") for s in active)
    refresh_label = "⏳ Yenile" if has_pending else "Yenile"
    rows: list[list] = []

    rows.append(
        [
            InlineKeyboardButton(
                "Otomatik: Açık" if auto_on else "Otomatik: Kapalı",
                callback_data="stat:toggle:auto",
            ),
            InlineKeyboardButton("Şimdi uygula", callback_data="stat:auto:now"),
        ]
    )

    prio_row: list = []
    for s in active[:3]:
        key = str(s.get("key") or "")
        if not key:
            continue
        prio_row.append(
            InlineKeyboardButton(
                skill_prio_button_label(key, is_primary=bool(s.get("is_primary"))),
                callback_data=f"stat:prio:{key}",
            )
        )
    if prio_row:
        rows.append(prio_row)

    rows.append(
        [
            InlineKeyboardButton("Elmas ile yükselt", callback_data="stat:uppri:diamond"),
            InlineKeyboardButton(refresh_label, callback_data="stat:refresh"),
        ]
    )

    if available > 0 and not auto_on:
        rows.append([InlineKeyboardButton("Pasif puanı harca", callback_data="stat:all")])

    rows.append([back_home_button()])
    return InlineKeyboardMarkup(rows)


def stat_board_callback_rows(analysis: dict) -> list[list[tuple[str, str]]]:
    auto_on = bool((analysis or {}).get("stat_auto_enabled", True))
    available = int((analysis or {}).get("available") or 0)
    has_pending = any(s.get("is_pending") for s in (analysis or {}).get("active_numbered") or [])
    refresh_label = "⏳ Yenile" if has_pending else "Yenile"
    rows: list[list[tuple[str, str]]] = [
        [
            ("Otomatik: Açık" if auto_on else "Otomatik: Kapalı", "stat:toggle:auto"),
            ("Şimdi uygula", "stat:auto:now"),
        ],
    ]
    for s in (analysis or {}).get("active_numbered") or []:
        key = str(s.get("key") or "")
        if key:
            rows.append([
                (
                    skill_prio_button_label(key, is_primary=bool(s.get("is_primary"))),
                    f"stat:prio:{key}",
                )
            ])
    rows.append([("Elmas ile yükselt", "stat:uppri:diamond"), (refresh_label, "stat:refresh")])
    if available > 0 and not auto_on:
        rows.append([("Pasif puanı harca", "stat:all")])
    rows.append([("Ana sayfa", "dash:home")])
    return rows


def resolve_active_skill_index(analysis: dict, index: int) -> str | None:
    numbered = analysis.get("active_numbered") or []
    pick = next((s for s in numbered if int(s.get("index") or 0) == index), None)
    return str(pick.get("key") or "") if pick else None


def resolve_passive_skill_key(analysis: dict, token: str) -> str | None:
    if (token or "").strip().isdigit():
        return resolve_passive_skill_index(analysis, int(token))
    norm = _norm_token(token)
    for s in analysis.get("passive_numbered") or []:
        key = str(s.get("key") or "")
        if norm in (_norm_token(key), _norm_token(str(s.get("name") or ""))):
            return key
    return resolve_active_skill_key(analysis, token)


def resolve_passive_skill_index(analysis: dict, index: int) -> str | None:
    numbered = analysis.get("passive_numbered") or []
    pick = next((s for s in numbered if int(s.get("index") or 0) == index), None)
    return str(pick.get("key") or "") if pick else None


def resolve_skill_index(analysis: dict, index: int) -> str | None:
    return resolve_active_skill_index(analysis, index) or resolve_passive_skill_index(analysis, index)
