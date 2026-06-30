"""Token süresi dolunca — yeniden bağlanma akışı."""

from __future__ import annotations

import html
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .token_console import CONSOLE_GRAB_TOKEN_ONELINER, format_console_script_telegram
from .version import get_version_label

_TOKEN_MARKERS = (
    "geçersiz",
    "invalid",
    "unauthorized",
    "unauthorised",
    "forbidden",
    "jwt",
    "token",
    "oturum",
    "expired",
    "süresi",
)


def is_token_auth_error(message: str | None, *, http_status: int | None = None) -> bool:
    if http_status in (401, 403):
        return True
    low = (message or "").lower()
    if not low:
        return False
    if "profile http 403" in low or "profile http 401" in low:
        return True
    if "http 403" in low or "http 401" in low:
        return True
    return any(m in low for m in _TOKEN_MARKERS)


def format_token_recovery_html(account_name: str | None = None) -> str:
    who = html.escape(account_name) if account_name else "hesabın"
    return (
        f"<b>🔑 Token yenileme</b> {get_version_label()}\n\n"
        f"<b>{who}</b> için oturum süresi dolmuş veya token geçersiz.\n"
        "Endişelenme — 4 adımda düzeltirsin:\n\n"
        "<b>1.</b> Oyuna gir → <a href=\"https://diplomacia.com.tr/\">diplomacia.com.tr</a>\n"
        "<b>2.</b> F12 → <b>Console</b> sekmesi\n"
        "<b>3.</b> Bir sonraki mesajdaki kodu yapıştır → Enter\n"
        "   • Çıkan <code>eyJ…</code> satırını kopyala\n"
        "<b>4.</b> Token'ı <b>bu sohbete</b> tek mesaj olarak yapıştır\n\n"
        "<i>Bot şimdi token'ını bekliyor — başka komut yazmana gerek yok.</i>\n"
        "<i>Pano hatası (NotAllowedError) olursa konsoldan elle kopyala.</i>"
    )


def token_recovery_markup(account_name: str) -> InlineKeyboardMarkup:
    name = account_name.strip().lower()
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔗 Oyuna git", url="https://diplomacia.com.tr/"),
                InlineKeyboardButton("📋 Konsol kodu", callback_data=f"connect:recover:{name}"),
            ],
            [InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")],
        ]
    )


def console_script_for_user() -> str:
    return format_console_script_telegram()


def extract_jwt_from_text(text: str) -> str | None:
    m = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", text or "")
    return m.group(0) if m else None
