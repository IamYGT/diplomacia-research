"""Kolay mod — hesap rolüne göre savaş UI / program metni."""

from __future__ import annotations

import html

from .account_config import get_config


def war_ui_enabled(account_name: str) -> bool:
    return bool(get_config(account_name).war_enabled)


def farm_program_idle_text(account_name: str) -> str:
    name = html.escape(account_name.strip().lower())
    return (
        f"<b>📋 Günlük program</b>\n\n"
        f"{name} için aktif program yok.\n\n"
        "Bot sırayla şunları yapar:\n"
        "1️⃣ Fabrikada çalışır (altın)\n"
        "2️⃣ Antrenman yapar\n\n"
        "<i>Başlamak için alttaki büyük butona bas.</i>"
    )


def default_program_idle_text(account_name: str) -> str:
    name = html.escape(account_name.strip().lower())
    return (
        f"<b>📋 Günlük program</b>\n\n"
        f"{name} için aktif program yok.\n\n"
        "Bot sırayla şunları yapar:\n"
        "1️⃣ Savaşa katılır\n"
        "2️⃣ Fabrikada çalışır (altın)\n"
        "3️⃣ Antrenman yapar\n\n"
        "<i>Başlamak için alttaki büyük butona bas.</i>"
    )


def append_farm_war_tab_note(text: str) -> str:
    """Farm hesap onboarding — savaş sekmesi izleme notu."""
    return (
        f"{text}\n"
        "<i>⚔️ <b>Savaş</b> sekmesi farm hesapta sadece izleme — katkı kapalı.</i>\n"
    )


def format_onboarding_done_tail(*, war_enabled: bool = True, keyboard_hidden: bool = False) -> str:
    """«Anladım» sonrası kısa yönlendirme — farm'da savaş butonu yok."""
    if keyboard_hidden:
        return "Üstteki <b>Ana | Savaş | Seyahat</b> sekmelerini kullan."
    if war_enabled:
        return (
            "Alttan bir butona bas:\n"
            "🌾 Altın Kazan · ⚔️ Savaşa Vur · ▶️ Programı Çalıştır"
        )
    return (
        "Alttan bir butona bas:\n"
        "🌾 Altın Kazan · ▶️ Programı Çalıştır\n"
        "<i>⚔️ Savaş sekmesi sadece izleme.</i>"
    )
