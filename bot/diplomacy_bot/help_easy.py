"""Kolay mod yardım metinleri."""

from __future__ import annotations

from .version import get_version_label


def format_help_easy_html() -> str:
    v = get_version_label()
    return (
        f"<b>❓ Kısa rehber</b> {v}\n\n"
        "<b>Üst sekmeler:</b> 🏠 Ana · ⚔️ Savaş · 🚶 Seyahat\n"
        "<i>Farm hesapta ⚔️ sekmesi sadece izleme — katkı kapalı.</i>\n"
        "<b>Alttaki butonlar:</b> isteğe bağlı — ⚙️ Ayarlar → ⌨️ Alttaki butonlar\n"
        "🌾 Altın · ▶️ Program · 💊 Can · 🎁 Günlük\n\n"
        "<b>Fabrika modları:</b>\n"
        "<code>/setfabric isim foreign</code> — bölge\n"
        "<code>/setfabric isim world</code> — dünya geneli (nomad)\n\n"
        "<b>Çok hesap:</b> ⚙️ → 👥 Diğer Hesaplar — panel güncellenir\n"
        "<b>Gazete:</b> <code>makale beğen</code> · <code>makale beğen aç</code>\n"
        "<b>Bağlantı:</b> /connect\n\n"
        "<i>🏠 Ana Sayfa tek mesaj; silersen yenisi açılır. Takılırsan 🔄 Yenile.</i>"
    )
