"""Filo yardım ve troubleshooting — /fleethelp, /help filo."""

from __future__ import annotations

from .config import MAX_ACCOUNTS_PER_USER
from .version import get_version_label


def format_fleet_help_html() -> str:
    limit = MAX_ACCOUNTS_PER_USER
    return (
        f"<b>📋 Filo komuta rehberi</b> {get_version_label()}\n\n"
        f"<b>Hızlı başlangıç ({limit} hesap)</b>\n"
        "<code>/fleetinbox</code> — token_inbox'tan toplu bağla\n"
        "<code>/fleetstart Hürmüz vote</code> — inbox + onar + kalıcı Hürmüz mission\n"
        "<code>/fleetaod</code> — bootstrap + fabrika + seyahat + ikamet\n"
        "<code>/fleetregion Hürmüz vote</code> — kalıcı bölge mission\n"
        "<code>/fleet audit</code> — otomasyon eksiklerini gör\n"
        "<code>/fleet repair</code> — eksik otomasyonları aç\n"
        "<code>/fleetvote</code> — aktif seçime oy\n"
        "<code>/fleet status</code> — detay tablo + 24s metrik\n\n"
        "<b>Token güvenliği</b>\n"
        "⚠️ JWT'yi sohbete yapıştırma — dosya kullan:\n"
        "<code>data/token_inbox/u{telegram_id}_01.jwt</code>\n\n"
        "<b>Panel</b>\n"
        "▶️ Başlat · 🇦🇴 AOD · 📋 Durum · ⚙️ İşlemler (alt menü + ◀️ geri)\n\n"
        "<b>Sorun giderme</b>\n"
        "• İkamet 400 → <code>/fleetresidence Hürmüz</code> tekrar\n"
        "• Fabrika fail → ana hesapta fabrika kur, <code>/fleetfactory main</code>\n"
        "• Inbox boş → dosya adı <code>u{uid}_*.jwt</code> olmalı\n"
        "• JWT süresi → <code>/loginkaydet</code> veya yeni token inbox\n"
        f"• {limit + 1}. hesap → limit <code>MAX_ACCOUNTS_PER_USER={limit}</code>\n\n"
        "<b>Otomasyon (opsiyonel)</b>\n"
        "<code>FLEET_INBOX_AUTO_SETUP=1</code> — yeni jwt → otomatik import+AOD\n\n"
        "<i>Detay: bot/docs/FLEET-COMMAND-CENTER.md</i>"
    )


def format_fleet_coach_hint() -> str:
    return "/fleethelp — token sohbete değil inbox · /fleetstart Hürmüz"
