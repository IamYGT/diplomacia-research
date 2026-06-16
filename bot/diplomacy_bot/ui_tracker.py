from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from telegram import Bot, InlineKeyboardMarkup
from telegram.error import BadRequest

log = logging.getLogger(__name__)

# Menü geçişleri — anında gösterilecek kısa metin
NAV_TRANSITION: dict[str, str] = {
    "dash:home": "🏠 Ana sayfaya dönülüyor…",
    "dash:refresh": "🔄 Panel güncelleniyor…",
    "menu:settings": "⚙️ Ayarlar açılıyor…",
    "menu:accounts": "👤 Hesaplar listeleniyor…",
    "menu:fleet": "👥 Filo açılıyor…",
    "menu:extras": "⋯ Ek menü açılıyor…",
    "nav:account": "👤 Hesap değiştiriliyor…",
    "keyboard:dashboard": "🏠 Ana sayfa açılıyor…",
    "keyboard:ayarlar": "⚙️ Ayarlar açılıyor…",
    "keyboard:filo": "👥 Filo açılıyor…",
    "keyboard:accounts": "👤 Hesaplar listeleniyor…",
    "action:hap": "💊 Can dolduruluyor…",
    "action:farm": "🌾 Farm çalışıyor…",
    "action:smartfarm": "🌾 Akıllı farm çalışıyor…",
    "action:stat": "⚡ Stat harcanıyor…",
    "action:daily": "🎁 Günlük ödül alınıyor…",
    "action:plan": "📋 Plan hazırlanıyor…",
    "action:quests": "📜 Görevler kontrol ediliyor…",
    "action:country": "🌍 Ülke seçiliyor…",
    "action:questlist": "📋 Görevler listeleniyor…",
    "action:wars": "⚔️ Savaş durumu alınıyor…",
    "action:warcontrib": "⚔️ Savaşa katkı veriliyor…",
    "action:training": "🏋️ Antrenman saldırısı…",
    "action:military": "🪖 Asker durumu alınıyor…",
    "action:myfactory": "🏭 Fabrika bilgisi alınıyor…",
    "action:farmboard": "🌾 Farm merkezi…",
    "action:craft": "🌾 Farm merkezi…",
    "action:countries": "🌍 Ülkeler listeleniyor…",
    "action:online": "🌐 Online sayısı alınıyor…",
    "action:autostatus": "🤖 Otomasyon durumu…",
    "action:stat": "⚡ Stat merkezi…",
    "action:statboard": "⚡ Stat merkezi…",
    "action:passive": "⚡ Stat merkezi…",
    "action:ping": "📡 Ping gönderiliyor…",
}


def tracker_footer(step: str) -> str:
    return f"\n\n<i>🔄 {step} — cevap birazdan iletilecek</i>"


def transition_text(key: str, *, extra: str = "") -> str:
    base = NAV_TRANSITION.get(key, "⏳ İşleniyor…")
    if extra:
        return f"{base}\n{extra}{tracker_footer('Hazırlanıyor')}"
    return f"{base}{tracker_footer('Hazırlanıyor')}"


async def edit_safe(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    *,
    parse_mode: str | None = "HTML",
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool | None = None,
) -> bool:
    kwargs: dict[str, Any] = {"text": text, "parse_mode": parse_mode}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    if disable_web_page_preview is not None:
        kwargs["disable_web_page_preview"] = disable_web_page_preview
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, **kwargs)
        return True
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            return True
        log.debug("edit_safe: %s", e)
        return False
    except Exception as e:
        log.debug("edit_safe failed: %s", e)
        return False


def spawn_tracked(
    application,
    coro: Awaitable[Any],
    *,
    name: str,
) -> asyncio.Task[Any]:
    """Arka plan görevi — menü tıklaması bloklanmasın."""

    async def _wrapper() -> Any:
        try:
            return await coro
        except Exception:
            log.exception("tracked task %s", name)
            return None

    return application.create_task(_wrapper(), name=name)
