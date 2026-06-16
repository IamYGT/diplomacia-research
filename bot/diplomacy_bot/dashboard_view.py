"""Dashboard görünüm — boş/hatalı snapshot'ta sahte sıfır gösterme."""

from __future__ import annotations

import html
from datetime import datetime, timezone

from .account_config import get_config, role_label
from .stealth_client import cooldown_remaining_sec
from .store import Account


def snap_is_live(snap: dict | None) -> bool:
    """Profil API'sinden gelmiş gerçek oyun verisi var mı."""
    if not snap or snap.get("error"):
        return False
    if snap.get("_live"):
        return True
    # Eski önbellek uyumu
    user = snap.get("username")
    if not user or user == "?":
        return False
    return "level" in snap


def format_dashboard_unavailable(acc: Account, snap: dict | None = None) -> str:
    """API yok / timeout / rate limit — yanıltıcı 0 altın gösterme."""
    snap = snap or {}
    cfg = get_config(acc.name)
    cd = cooldown_remaining_sec()
    err = str(snap.get("error") or "").strip()
    af = "🟢 Açık" if snap.get("autofarm") or acc.autofarm else "⚪ Kapalı"

    lines = [
        f"<b>🔴 {html.escape(acc.name)}</b> — <i>canlı oyun verisi alınamadı</i>",
        "",
    ]
    if cd > 0:
        lines.append(f"⏳ <b>API limiti</b> — {cd} sn bekleyin, sonra <b>🔄 Yenile</b>")
    if err:
        lines.append(f"⚠️ {html.escape(err[:120])}")
    if not cd and not err:
        lines.append("⚠️ Sunucuya ulaşılamadı — biraz sonra <b>🔄 Yenile</b>")

    lines.extend(
        [
            "",
            "<b>🤖 Bot (yerel ayar)</b>",
            f"Otomatik farm: {af}",
            f"Görev: <b>{role_label(cfg.role)}</b> · {html.escape(cfg.work_mode)}",
        ]
    )
    if cfg.is_premium_hub:
        lines.append("Merkez hesap")
    lines.append(
        f"\n<i>🕐 {datetime.now(timezone.utc).strftime('%H:%M')} UTC · önbellek yok veya geçersiz</i>"
    )
    return "\n".join(lines)


def install_dashboard_format_patch() -> None:
    from . import telegram_ui

    if getattr(telegram_ui, "_dashboard_format_patched", False):
        return
    orig = telegram_ui.format_dashboard_html

    def wrapped(acc: Account, snap=None) -> str:
        row = snap if snap is not None else orig.__globals__.get("snapshot_account")
        if snap is None:
            from .dynamic_context import snapshot_account

            row = snapshot_account(acc)
        if not snap_is_live(row):
            return format_dashboard_unavailable(acc, row)
        return orig(acc, row)

    telegram_ui.format_dashboard_html = wrapped
    telegram_ui._dashboard_format_patched = True
