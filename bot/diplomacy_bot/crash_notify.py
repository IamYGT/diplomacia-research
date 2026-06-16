from __future__ import annotations

import html
import os
import socket
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any

import requests

from .config import TELEGRAM_ADMIN_IDS, TELEGRAM_BOT_TOKEN
from .version import get_version_label

_DEDUPE: dict[str, float] = {}
_COOLDOWN_SEC = int(os.environ.get("CRASH_NOTIFY_COOLDOWN_SEC", "90"))
_MAX_LEN = 4000


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _host() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "?"


def format_crash_report(
    title: str,
    detail: str = "",
    *,
    exc: BaseException | None = None,
    tb: str = "",
    extra: dict[str, Any] | None = None,
    update_summary: str = "",
) -> str:
    lines = [
        f"<b>🚨 {html.escape(title)}</b>",
        f"<code>{get_version_label()}</code> · <code>{html.escape(_host())}</code>",
        f"🕐 {_now()}",
        "",
    ]
    if detail:
        lines.append(f"<b>Detay</b>\n<pre>{html.escape(detail[:1200])}</pre>")
    if exc is not None:
        lines.append(f"<b>Exception</b>\n<code>{html.escape(type(exc).__name__)}: {html.escape(str(exc)[:500])}</code>")
    if update_summary:
        lines.append(f"<b>Update</b>\n<pre>{html.escape(update_summary[:800])}</pre>")
    if extra:
        kv = "\n".join(f"• {html.escape(str(k))}: <code>{html.escape(str(v)[:200])}</code>" for k, v in extra.items())
        lines.append(f"<b>Context</b>\n{kv}")
    if tb:
        lines.append(f"<b>Traceback</b>\n<pre>{html.escape(tb[-2500:])}</pre>")
    lines.append("\n<i>PM2/log kontrol et · Windows 409 Conflict varsa eski botu kapat</i>")
    text = "\n".join(lines)
    if len(text) > _MAX_LEN:
        text = text[: _MAX_LEN - 20] + "\n…</pre>"
    return text


def _should_send(dedupe_key: str) -> bool:
    now = time.time()
    last = _DEDUPE.get(dedupe_key, 0)
    if now - last < _COOLDOWN_SEC:
        return False
    _DEDUPE[dedupe_key] = now
    return True


def send_crash_notify(
    title: str,
    detail: str = "",
    *,
    exc: BaseException | None = None,
    tb: str = "",
    extra: dict[str, Any] | None = None,
    update_summary: str = "",
    dedupe_key: str | None = None,
) -> bool:
    """Senkron Telegram bildirimi — bot/PTB çökse bile requests ile gönderir."""
    token = (TELEGRAM_BOT_TOKEN or "").strip()
    if not token or token == "your_bot_token_here":
        print(f"[crash_notify] token yok — {title}: {detail}", file=sys.stderr)
        return False
    if not TELEGRAM_ADMIN_IDS:
        print(f"[crash_notify] admin yok — {title}", file=sys.stderr)
        return False

    key = dedupe_key or f"{title}:{detail[:80]}:{type(exc).__name__ if exc else ''}"
    if not _should_send(key):
        return False

    if exc and not tb:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    text = format_crash_report(
        title,
        detail,
        exc=exc,
        tb=tb,
        extra=extra,
        update_summary=update_summary,
    )
    ok = False
    for chat_id in TELEGRAM_ADMIN_IDS:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=15,
            )
            data = r.json()
            if data.get("ok"):
                ok = True
            else:
                print(f"[crash_notify] send fail {chat_id}: {data}", file=sys.stderr)
        except Exception as e:
            print(f"[crash_notify] request error: {e}", file=sys.stderr)
    return ok


def summarize_update(update: object) -> str:
    try:
        from telegram import Update

        if not isinstance(update, Update):
            return str(update)[:200]
        parts = []
        if update.effective_user:
            parts.append(f"user_id={update.effective_user.id}")
        if update.callback_query and update.callback_query.data:
            parts.append(f"callback={update.callback_query.data}")
        if update.message and update.message.text:
            parts.append(f"text={update.message.text[:120]}")
        return " | ".join(parts) or "update"
    except Exception:
        return repr(update)[:200]


def install_crash_hooks() -> None:
    """sys.excepthook — import/startup fatal hataları."""

    def _hook(exc_type, exc, tb_obj):
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc, tb_obj)
            return
        tb = "".join(traceback.format_exception(exc_type, exc, tb_obj))
        send_crash_notify(
            "Bot fatal crash (excepthook)",
            "İşlenmeyen exception — process sonlanıyor",
            exc=exc if isinstance(exc, BaseException) else None,
            tb=tb,
            dedupe_key=f"excepthook:{exc_type.__name__}",
        )
        sys.__excepthook__(exc_type, exc, tb_obj)

    sys.excepthook = _hook
