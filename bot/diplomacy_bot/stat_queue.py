"""Stat kuyruk — cooldown bitince cron gibi sonraki yükseltmeyi tetikler."""

from __future__ import annotations

import logging
import time
from typing import Any

from .account_config import AccountConfig, get_config, normalize_role
from .account_runtime import account_context
from .dynamic_context import invalidate_snapshot_cache
from .modules import stats
from .store import Account, list_accounts
from .config import STAT_QUEUE_INTERVAL_SEC
from .stealth_client import cooldown_remaining_sec

log = logging.getLogger(__name__)

_WAKE_GRACE_SEC = 2.0
_MIN_RUN_GAP_SEC = 8.0

_WAKE_AT: dict[str, float] = {}
_LAST_RUN: dict[str, float] = {}


def _has_ready_skill(active: dict, cfg: AccountConfig) -> bool:
    """Öncelikte pending olmayan (hemen yükseltilebilir) skill var mı."""
    if not isinstance(active, dict):
        return False
    keys = [k for k in active if isinstance(k, str) and "_pending" not in k]
    if not keys:
        return False
    for skill in stats.resolve_active_priority(cfg, keys):
        if not stats.skill_is_pending(active, skill):
            return True
    return False


def note_pending_wake(
    account_name: str,
    *,
    pending_at: str | None = None,
    cooldown_ms: int | None = None,
) -> None:
    """Yükseltme başladı — cooldown bitince tekrar dene."""
    name = account_name.strip().lower()
    sec = None
    if pending_at:
        sec = stats.seconds_until_pending_at(pending_at)
        if sec is not None and sec <= 0:
            sec = _WAKE_GRACE_SEC
    if sec is None and cooldown_ms:
        sec = max(1, int(cooldown_ms) // 1000)
    if sec is not None:
        _WAKE_AT[name] = time.time() + sec + _WAKE_GRACE_SEC
    else:
        _WAKE_AT[name] = time.time() + _MIN_RUN_GAP_SEC


def is_wake_due(account_name: str) -> bool:
    name = account_name.strip().lower()
    now = time.time()
    if now - _LAST_RUN.get(name, 0) < _MIN_RUN_GAP_SEC:
        return False
    return now >= _WAKE_AT.get(name, 0)


def _gap_seconds_remaining(account_name: str) -> int:
    name = account_name.strip().lower()
    elapsed = time.time() - _LAST_RUN.get(name, 0)
    return max(0, int(_MIN_RUN_GAP_SEC - elapsed + 0.999))


def _estimate_wake_seconds(active: dict, account_name: str) -> int:
    """State okuma — _WAKE_AT yoksa profilden tahmin (yazmaz)."""
    name = account_name.strip().lower()
    wake_at = _WAKE_AT.get(name)
    if wake_at is not None:
        return max(0, int(wake_at - time.time() + 0.999))
    nearest = stats.nearest_pending_seconds(active)
    if nearest is not None and nearest > 0:
        return int(nearest + _WAKE_GRACE_SEC)
    return STAT_QUEUE_INTERVAL_SEC


def _priority_keys(active: dict) -> list[str]:
    if not isinstance(active, dict):
        return []
    return [k for k in active if isinstance(k, str) and "_pending" not in k]


def _queue_skill_context(active: dict, cfg: AccountConfig) -> dict[str, Any]:
    """Pending / sıradaki hazır skill — panel metni için."""
    from .stat_board import skill_short_name

    keys = _priority_keys(active)
    priority = stats.resolve_active_priority(cfg, keys)
    pending_key = None
    pending_sec = None
    for skill in priority:
        if stats.skill_is_pending(active, skill):
            pending_key = skill
            pending_sec = stats.pending_seconds_remaining(active, skill)
            break
    next_key = None
    for skill in priority:
        if not stats.skill_is_pending(active, skill):
            next_key = skill
            break
    return {
        "pending_key": pending_key,
        "pending_name": skill_short_name(pending_key) if pending_key else None,
        "pending_seconds": pending_sec,
        "next_key": next_key,
        "next_name": skill_short_name(next_key) if next_key else None,
    }


def _format_queue_summary(
    *,
    kind: str,
    sec: int,
    ctx: dict[str, Any],
    ready_skill: bool,
) -> str:
    pending_name = ctx.get("pending_name")
    next_name = ctx.get("next_name")

    if ready_skill and next_name:
        if sec <= 0:
            return f"{next_name} hazır — en geç {STAT_QUEUE_INTERVAL_SEC} sn içinde otomatik"
        return f"{next_name} hazır — {sec} sn sonra otomatik"

    if pending_name:
        time_part = f"{sec} sn"
        if next_name and next_name != pending_name:
            return f"{pending_name} bitince → {next_name} · {time_part}"
        return f"{pending_name} bitince → {time_part}"

    if sec <= 0:
        if kind == "due":
            return "Cooldown bitti — otomatik denenecek"
        return f"Hazır — en geç {STAT_QUEUE_INTERVAL_SEC} sn içinde otomatik"
    return f"{sec} sn sonra otomatik"


def preview_stat_queue(
    active: dict,
    cfg: AccountConfig,
    account_name: str | None = None,
) -> dict[str, Any]:
    """Panel — should_tick_now kararının okunabilir özeti (yan etkisiz)."""
    acct = (account_name or cfg.account_name or "x").strip().lower()
    if not cfg.stat_auto_enabled or normalize_role(cfg.role) == "off":
        return {
            "kind": "disabled",
            "ready_now": False,
            "seconds_until": None,
            "summary": "Otomatik kapalı",
        }

    gap = _gap_seconds_remaining(acct)
    ready_skill = _has_ready_skill(active, cfg)
    ctx = _queue_skill_context(active, cfg)

    if ready_skill:
        sec = gap
        kind = "ready" if sec <= 0 else "ready_gap"
        return {
            "kind": kind,
            "ready_now": sec <= 0,
            "seconds_until": sec,
            "summary": _format_queue_summary(kind=kind, sec=sec, ctx=ctx, ready_skill=True),
            "pending_name": ctx.get("pending_name"),
            "next_name": ctx.get("next_name"),
        }

    wake_sec = _estimate_wake_seconds(active, acct)
    sec = max(gap, wake_sec)
    kind = "due" if sec <= 0 else "waiting"
    return {
        "kind": kind,
        "ready_now": sec <= 0,
        "seconds_until": sec,
        "summary": _format_queue_summary(kind=kind, sec=sec, ctx=ctx, ready_skill=False),
        "pending_name": ctx.get("pending_name"),
        "next_name": ctx.get("next_name"),
    }


def should_tick_now(active: dict, cfg: AccountConfig, account_name: str) -> bool:
    """Hazır skill varsa bekleme; yoksa cooldown uyanmasını bekle."""
    name = account_name.strip().lower()
    now = time.time()
    if now - _LAST_RUN.get(name, 0) < _MIN_RUN_GAP_SEC:
        return False
    if _has_ready_skill(active, cfg):
        return True
    if name not in _WAKE_AT:
        nearest = stats.nearest_pending_seconds(active)
        if nearest is not None and nearest > 0:
            _WAKE_AT[name] = now + nearest + _WAKE_GRACE_SEC
        else:
            _WAKE_AT[name] = 0.0
    return now >= _WAKE_AT.get(name, 0)


def tick_stat_queue(acc: Account) -> dict | None:
    """Tek hesap — sıradaki hazır stat veya cooldown bitince yükselt."""
    cfg = get_config(acc.name)
    if not cfg.stat_auto_enabled or normalize_role(cfg.role) == "off":
        return None

    # Rate limit aktifse upgrade/profile deneme — cooldown bitene kadar bekle.
    # Yoksa her tick 429 alıp _last_429_at yeniler → cooldown sonsuz döngü + dashboard boş snapshot.
    if cooldown_remaining_sec() > 0:
        return None

    with account_context(acc):
        active = stats.get_active_skills(acc.token)

    if not should_tick_now(active, cfg, acc.name):
        return None

    with account_context(acc):
        result = stats.run_stat_automation(acc.token, cfg)
        active_after = stats.get_active_skills(acc.token)

    name = acc.name.strip().lower()
    _LAST_RUN[name] = time.time()
    upgraded = False
    for u in result.get("upgrades") or []:
        if u.get("ok"):
            upgraded = True
            note_pending_wake(
                acc.name,
                pending_at=u.get("pending_at"),
                cooldown_ms=u.get("cooldown_ms"),
            )
            break
    if upgraded:
        invalidate_snapshot_cache(acc.name)
        return result

    if stats.any_skill_pending(active_after) and not _has_ready_skill(active_after, cfg):
        nearest = stats.nearest_pending_seconds(active_after)
        if nearest is not None and nearest > 0:
            _WAKE_AT[name] = time.time() + nearest + _WAKE_GRACE_SEC
    elif _has_ready_skill(active_after, cfg):
        _WAKE_AT[name] = time.time() + _MIN_RUN_GAP_SEC
    else:
        _WAKE_AT[name] = time.time() + STAT_QUEUE_INTERVAL_SEC
    invalidate_snapshot_cache(acc.name)
    return result


def accounts_for_stat_queue() -> list[Account]:
    out: list[Account] = []
    for acc in list_accounts():
        cfg = get_config(acc.name)
        if not cfg.stat_auto_enabled:
            continue
        if normalize_role(cfg.role) == "off":
            continue
        out.append(acc)
    return out
