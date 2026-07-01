"""Dinamik coach dashboard — sabit şablon yerine öncelik skorlu tek ekran."""

from __future__ import annotations

import html
import time
from dataclasses import dataclass

from .account_config import get_config, role_label
from .dynamic_context import snapshot_account, snapshot_cache_age_sec
from .health_sync import health_dashboard_banner, premium_auto_work_note, snap_health
from .auth import scoped_list_accounts
from .stealth_client import cooldown_remaining_sec
from .store import Account
from .tick_activity import format_activity_line
from .user_errors import format_ms
from .version import get_version_label
from .config import TOKEN_REFRESH_LEAD_SEC
from .jwt_meta import format_expiry_human, is_expired, is_expiring_soon


@dataclass
class CoachCue:
    score: int
    pulse: str
    action: str
    hint: str = ""


def _bar(pct: int, width: int = 8) -> str:
    pct = max(0, min(100, pct))
    filled = round(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def score_coach_cues(snap: dict, acc: Account) -> list[CoachCue]:
    """Duruma göre sıralı ipuçları — en yüksek skor üstte."""
    cues: list[CoachCue] = []
    cfg = get_config(acc.name)
    health = snap_health(snap)

    tok = acc.token or ""
    if tok.startswith("eyJ"):
        if is_expired(tok):
            cues.append(
                CoachCue(
                    98,
                    "Token süresi dolmuş — farm durabilir",
                    "🔑 Token yenile",
                    "/loginkaydet veya token yapıştır",
                )
            )
        elif is_expiring_soon(tok, lead_sec=TOKEN_REFRESH_LEAD_SEC):
            cues.append(
                CoachCue(
                    92,
                    f"Token {format_expiry_human(tok)} sonra doluyor",
                    "🔑 Otomatik yenileme",
                    "loginkaydet veya data/token_inbox",
                )
            )

    if acc.telegram_user_id:
        siblings = scoped_list_accounts(acc.telegram_user_id)
        if len(siblings) >= 2:
            cues.append(
                CoachCue(
                    72,
                    f"{len(siblings)} hesaplı filo aktif",
                    "📋 Filo komuta",
                    "/fleethelp — token inbox kullan · /fleetaod",
                )
            )

    pills = int(snap.get("pills") or 0)
    passive = int(snap.get("passive_available") or 0)
    qc = int(snap.get("quests_claimable") or 0)
    daily_ok = snap.get("daily_claimed")
    daily_avail = snap.get("daily_available", daily_ok is not True)

    if health <= 0 and pills > 0:
        cues.append(CoachCue(100, "Can kritik — farm durmuş olabilir", "💊 Can Doldur", "hap hazır"))
    elif health < 50 and pills > 0:
        cues.append(CoachCue(90, "Can düşük — önce canını toparla", "💊 Can Doldur", f"{health}/100"))

    if daily_avail and daily_ok is not True:
        cues.append(CoachCue(85, "Günlük ödün alınmadı", "🎁 Günlük Ödül", "autofarm açıksa otomatik alınır"))

    if qc > 0:
        cues.append(
            CoachCue(
                80,
                f"{qc} görev ödülü hazır",
                "📜 Görev topla",
                "autofarm açıksa otomatik toplanır",
            )
        )

    if passive > 0 and cfg.stat_auto_enabled:
        cues.append(CoachCue(70, f"{passive} pasif stat bekliyor", "⚡ Statlar", "otomatik harcanıyor"))

    if snap.get("training_ready"):
        cues.append(CoachCue(65, "Ücretsiz antrenman hazır", "🏋️ Antrenman", "program veya autofarm"))

    if int(snap.get("war_active") or 0) > 0 and cfg.war_enabled:
        cues.append(CoachCue(60, "Açık savaş var", "⚔️ Savaşa Vur", "katkı yap"))

    if snap.get("work_ready") and not (snap.get("premium") and snap.get("auto_work_active")):
        cues.append(CoachCue(55, "Fabrika boş — altın kazanabilirsin", "🌾 Altın Kazan", "tek tık work"))

    work_ms = int(snap.get("work_wait_ms") or 0)
    if work_ms > 0 and not (snap.get("premium") and snap.get("auto_work_active")):
        cues.append(
            CoachCue(
                40,
                f"Fabrika {format_ms(work_ms)} sonra hazır",
                "⏳ Bekle",
                "bu sürede görev/stat",
            )
        )

    if snap.get("premium") and snap.get("auto_work_active"):
        cues.append(CoachCue(35, "Premium sunucu farm yapıyor", "⭐ Auto-work", "manuel farm gerekmez"))

    if not acc.autofarm:
        cues.append(CoachCue(30, "7/24 bot kapalı", "▶️ Autofarm aç", "ayarlar veya /autofarm on"))

    if not cues:
        if acc.autofarm:
            cues.append(CoachCue(10, "Her şey yolunda — bot arka planda", "🏠 İzle", "~10 dk aralıkla tick"))
        else:
            cues.append(CoachCue(10, "Hesap hazır", "▶️ Programı Çalıştır", "veya autofarm aç"))

    cues.sort(key=lambda c: c.score, reverse=True)
    return cues


def format_coach_dashboard(acc: Account, snap: dict | None = None) -> str:
    """Öncelik skorlu kompakt panel — sabit «Şimdi ne yapmalı» listesi yok."""
    snap = snap or snapshot_account(acc)
    cfg = get_config(acc.name)
    cues = score_coach_cues(snap, acc)
    top = cues[0]
    secondary = cues[1].action if len(cues) > 1 else ""

    health = snap_health(snap)
    balance = int(snap.get("balance") or 0)
    diamonds = int(snap.get("diamonds") or 0)
    pills = int(snap.get("pills") or 0)
    af = "🟢" if snap.get("autofarm") or acc.autofarm else "⚪"

    chips: list[str] = []
    if int(snap.get("quests_claimable") or 0):
        chips.append(f"📜{snap['quests_claimable']}")
    if snap.get("daily_available") and not snap.get("daily_claimed"):
        chips.append("🎁günlük")
    if snap.get("training_ready"):
        chips.append("🏋️")
    if snap.get("work_ready"):
        chips.append("🌾")
    chip_line = " ".join(chips)

    age = snapshot_cache_age_sec(acc.name)
    age_note = f"{int(age)}sn" if age is not None else "şimdi"
    cd = cooldown_remaining_sec()

    lines = [
        f"<b>{html.escape(str(snap.get('username') or acc.name))}</b>"
        f" · <code>{html.escape(acc.name)}</code>"
        f" · Lv{snap.get('level', '?')}"
        f" · {html.escape(str(snap.get('province') or '?'))}",
    ]

    if acc.telegram_user_id:
        siblings = scoped_list_accounts(acc.telegram_user_id)
        if len(siblings) > 1:
            tags = []
            for s in siblings[:4]:
                mark = f"⭐{s.name}" if s.name == acc.name else s.name
                tags.append(html.escape(mark))
            extra = f" +{len(siblings) - 4}" if len(siblings) > 4 else ""
            lines.append(f"<i>👤 {len(siblings)} hesap: {' · '.join(tags)}{extra}</i>")
        else:
            lines.insert(
                1,
                f"<i>⭐ Aktif: <code>{html.escape(acc.name)}</code></i>",
            )

    lines.extend(
        [
            f"💰 {balance:,} · 💎 {diamonds:,} · ❤️ {_bar(health)} {health} · 💊 {pills}",
            f"<b>📡 {html.escape(top.pulse)}</b>",
            f"→ <b>{html.escape(top.action)}</b>"
            + (f" · sonra <i>{html.escape(secondary)}</i>" if secondary else ""),
        ]
    )
    if top.hint:
        lines.append(f"<i>{html.escape(top.hint)}</i>")
    if chip_line:
        lines.append(f"<i>Hazır: {chip_line}</i>")

    activity = format_activity_line(acc.name)
    if activity:
        lines.append(f"<i>🤖 {html.escape(activity)}</i>")

    tok = acc.token or ""
    if tok.startswith("eyJ"):
        human = format_expiry_human(tok)
        if is_expired(tok):
            lines.append("🔑 Token: <b>dolmuş</b> — yenilemen gerek")
        elif is_expiring_soon(tok, lead_sec=86400):
            lines.append(f"🔑 Token kalan: <b>{human}</b> — yakında otomatik yenilenecek")
        else:
            lines.append(f"🔑 Token kalan: <b>{human}</b>")

    meta = f"{get_version_label()} · {af} autofarm · {role_label(cfg.role)} · veri {age_note}"
    if cd > 0:
        meta += f" · API {cd}sn"
    lines.append(f"<i>{meta}</i>")

    banner = health_dashboard_banner(snap)
    prem = premium_auto_work_note(snap)
    prefix = "\n".join(p for p in (banner, prem) if p)
    body = "\n".join(lines)
    return f"{prefix}\n{body}" if prefix else body


def install_dashboard_coach_patch() -> None:
    """Kolay mod + eski uzun dashboard yerine coach kartı."""
    from . import telegram_ui as ui
    from .dashboard_view import format_dashboard_unavailable, snap_is_live

    if getattr(ui, "_coach_dashboard_installed", False):
        return

    _orig = ui.format_dashboard_html

    def format_dashboard_coach(acc: Account, snap=None) -> str:
        row = snap
        if row is None:
            row = snapshot_account(acc)
        if not snap_is_live(row):
            return _orig(acc, snap)
        return format_coach_dashboard(acc, row)

    ui.format_dashboard_html = format_dashboard_coach  # type: ignore[assignment]
    ui._coach_dashboard_installed = True
