"""Canlı bildirim — snapshot diff ile olay tespit + Telegram push.

alert_watch_job her hesabın snapshot cache'ini diff'ler:
- health düştü → saldırıya uğradı
- level arttı → level up
- balance büyük düştü → dikkat
State data/alert_state.json (son bilinen health/level/balance per account).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from telegram.ext import ContextTypes

from .config import DATA_DIR
from .event_notify import notify_event
from .health_state import load_health_state, save_health_state, update_account_row
from .store import Account, list_accounts

log = logging.getLogger(__name__)

_STATE_FILE: Path = DATA_DIR / "alert_state.json"
_HEALTH_DROP_THRESHOLD = 10  # >=10 health düşüşü = saldırı sinyali
_BALANCE_DROP_THRESHOLD = 0.25  # %25+ bakiye düşüşü = dikkat


def _load_state() -> dict:
    try:
        return json.loads(_STATE_FILE.read_text()) if _STATE_FILE.exists() else {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_FILE.write_text(json.dumps(state))
    except Exception as e:
        log.warning("alert_state save: %s", e)


def _num(snap: dict, key: str) -> int:
    try:
        return int(snap.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def diff_events(acc: Account, snap: dict, state: dict) -> list[dict]:
    """Snapshot'ı önceki state ile karşılaştır → olay listesi.

    snap cache (peek_snapshot_cache allow_stale). state mutable (yeni değerlerle güncellenir).
    """
    events: list[dict] = []
    if not snap or snap.get("error"):
        return events

    name = acc.name.strip().lower()
    prev = state.get(name) or {}
    health = _num(snap, "health")
    level = _num(snap, "level")
    balance = _num(snap, "balance")
    pill_cd = int(snap.get("pill_cooldown_ms") or 0)

    if prev:
        prev_health = prev.get("health", health)
        prev_level = prev.get("level", level)
        prev_balance = prev.get("balance", balance)

        drop = prev_health - health
        if drop >= _HEALTH_DROP_THRESHOLD:
            events.append({
                "key": f"attack:{name}:{int(time.time() // 3600)}",  # saatlik dedup
                "title": f"⚔️ {acc.username or name} saldırıya uğradı",
                "body": f"❤️ Can {prev_health} → {health} (-{drop})",
            })

        if level > prev_level:
            events.append({
                "key": f"levelup:{name}:{level}",
                "title": f"🎉 {acc.username or name} seviye atladı",
                "body": f"Seviye {prev_level} → {level}",
            })

        if prev_balance > 0:
            bal_drop = prev_balance - balance
            if bal_drop > 0 and bal_drop / prev_balance >= _BALANCE_DROP_THRESHOLD:
                events.append({
                    "key": f"spend:{name}:{int(time.time() // 3600)}",
                    "title": f"💰 {acc.username or name} büyük harcama",
                    "body": f"Bakiye {prev_balance:,} → {balance:,}",
                })

    state[name] = {
        "health": health,
        "level": level,
        "balance": balance,
        "pill_cooldown_ms": pill_cd,
    }
    return events


async def alert_watch_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduler job — her hesap snapshot diff + olay push. API çağırmaz (cache okur)."""
    from .dynamic_context import peek_snapshot_cache

    state = load_health_state()
    legacy = _load_state()
    for k, v in legacy.items():
        if k not in state and isinstance(v, dict):
            state[k] = v
    for acc in list_accounts():
        try:
            snap = peek_snapshot_cache(acc.name, allow_stale=True)
            events = diff_events(acc, snap or {}, state)
            for ev in events:
                chat_id = acc.telegram_user_id
                if chat_id:
                    notify_event(chat_id, ev["key"], ev["title"], ev["body"])
        except Exception as e:
            log.warning("alert_watch %s: %s", acc.name, e)
    save_health_state(state)

