"""Telegram event push helper — user-scoped bildirim (crash_notify pattern).

Feature'lar (event_alerts, daily_report, intel) ortak push + dedup kullanır.
crash_notify admin'e, event_notify kullanıcıya (hesap sahibi chat_id).
"""

from __future__ import annotations

import logging
import time

import requests

from .config import TELEGRAM_ADMIN_IDS, TELEGRAM_BOT_TOKEN

log = logging.getLogger(__name__)

# dedup: aynı event_key 5dk (300sn) içinde tek push
_DEDUP_SEC = 300
_LAST_NOTIFY: dict[str, float] = {}


def _bot_token() -> str:
    return TELEGRAM_BOT_TOKEN or ""


def _is_within_cooldown(event_key: str) -> bool:
    last = _LAST_NOTIFY.get(event_key)
    if last is None:
        return False
    return time.time() - last < _DEDUP_SEC


def _mark_sent(event_key: str) -> None:
    _LAST_NOTIFY[event_key] = time.time()
    # büyümesini önle — eski kayıtları temizle
    cutoff = time.time() - _DEDUP_SEC * 4
    for k in [k for k, t in _LAST_NOTIFY.items() if t < cutoff]:
        _LAST_NOTIFY.pop(k, None)


def send_telegram_message(chat_id: int, text: str) -> bool:
    """Düşük seviye Telegram gönderi — sendMessage API. Başarı bool döner."""
    token = _bot_token()
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        data = r.json()
        if not data.get("ok"):
            log.warning("event_notify send fail %s: %s", chat_id, data)
            return False
        return True
    except Exception as e:
        log.warning("event_notify request error: %s", e)
        return False


def notify_event(
    chat_id: int,
    event_key: str,
    title: str,
    body: str,
    *,
    also_admin: bool = False,
) -> bool:
    """User-scoped bildirim + dedup.

    event_key: aynı olay 5dk içinde tekrar push edilmez (örn "war:ygt:123").
    title: başlık (bold), body: detay.
    also_admin: admin'lere de gönder (crash_notify benzeri).
    """
    if _is_within_cooldown(event_key):
        return False
    text = f"<b>{title}</b>\n{body}" if body else f"<b>{title}</b>"
    ok = send_telegram_message(chat_id, text)
    if also_admin:
        for admin_id in TELEGRAM_ADMIN_IDS:
            if admin_id != chat_id:
                send_telegram_message(admin_id, text)
    if ok:
        _mark_sent(event_key)
    return ok


def reset_dedup(event_key: str | None = None) -> None:
    """Test/event zorla tetikleme için dedup temizle."""
    if event_key is None:
        _LAST_NOTIFY.clear()
    else:
        _LAST_NOTIFY.pop(event_key, None)
