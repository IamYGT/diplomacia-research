"""Hap cooldown bitince Telegram bildirimi — health_watch_state."""

from __future__ import annotations

import logging
import time

from telegram.ext import ContextTypes

from .event_notify import notify_event, pill_ready_reply_markup
from .health_state import account_row, load_health_state, save_health_state, update_account_row
from .health_sync import work_health
from .modules.economy import get_auto_status
from .store import list_accounts

log = logging.getLogger(__name__)


def check_pill_cooldown_cleared(
    account_name: str,
    *,
    pill_cooldown_ms: int,
    health: int,
    pills: int,
    prev_cd: int | None,
) -> dict | None:
    """CD 0'a düştüyse bildirim olayı (yoksa None)."""
    if prev_cd is None:
        return None
    if prev_cd <= 0 or pill_cooldown_ms > 0:
        return None
    if health >= 100 or pills <= 0:
        return None
    name = account_name.strip().lower()
    return {
        "key": f"pill_ready:{name}:{int(time.time() // 300)}",
        "title": f"💊 {account_name} — hap kullanılabilir",
        "body": (
            f"Can {health}/100 · {pills:,} hap hazır\n"
            "Aşağıdaki butonlarla devam et veya <code>hap kullan</code> yaz"
        ),
        "with_markup": True,
    }


async def pill_cooldown_watch_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """~90 sn — hap CD bitişini izle, kullanıcıya push."""
    from .game_api import get_profile

    state = load_health_state()
    dirty = False
    for acc in list_accounts():
        if not acc.telegram_user_id:
            continue
        name = acc.name.strip().lower()
        try:
            status = get_auto_status(acc.token) or {}
            cd = int(status.get("pill_cooldown_ms") or 0)
            prev_row = account_row(state, name)
            prev_cd = prev_row.get("pill_cooldown_ms")
            health = work_health(acc.token, auto_status=status)
            pills = int(status.get("health_pills") or 0)
            try:
                pills = max(pills, int(get_profile(acc.token).health_pills or 0))
            except Exception:
                pass
            ev = check_pill_cooldown_cleared(
                acc.username or acc.name,
                pill_cooldown_ms=cd,
                health=health,
                pills=pills,
                prev_cd=prev_cd if prev_cd is not None else cd,
            )
            if ev:
                markup = pill_ready_reply_markup() if ev.get("with_markup") else None
                notify_event(
                    acc.telegram_user_id,
                    ev["key"],
                    ev["title"],
                    ev["body"],
                    reply_markup=markup,
                )
                dirty = True
                log.info("pill_cd_ready acc=%s health=%s pills=%s", acc.name, health, pills)
            if prev_row.get("pill_cooldown_ms") != cd or prev_row.get("health") != health:
                dirty = True
            update_account_row(state, name, pill_cooldown_ms=cd, health=health, pills=pills)
        except Exception as e:
            log.warning("pill_cd_watch %s: %s", acc.name, e)
    if dirty:
        save_health_state(state)
