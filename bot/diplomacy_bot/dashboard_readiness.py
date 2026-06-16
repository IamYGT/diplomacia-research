"""Dashboard snapshot — readiness (60 sn cache)."""

from __future__ import annotations

import time

from .account_config import get_config
from .readiness_probes import (
    READINESS_CACHE_SEC,
    build_readiness_from_probes,
    probe_readiness_light,
    readiness_fields,
)
from .stat_queue import preview_stat_queue
from .store import Account

from .dashboard_markup import install_dashboard_markup_patch
from .dashboard_publish import install_dashboard_publish_patch
from .dashboard_view import install_dashboard_format_patch

install_dashboard_markup_patch()
install_dashboard_publish_patch()
install_dashboard_format_patch()

_READINESS_CACHE: dict[str, tuple[float, dict[str, object]]] = {}


def invalidate_readiness_cache(account_name: str | None = None) -> None:
    if account_name:
        _READINESS_CACHE.pop(account_name.strip().lower(), None)
    else:
        _READINESS_CACHE.clear()


def _apply_stat_queue(row: dict, acc: Account) -> None:
    cfg = get_config(acc.name)
    skills = row.get("active_skills") or {}
    if isinstance(skills, dict) and cfg.stat_auto_enabled:
        qs = preview_stat_queue(skills, cfg, acc.name)
        row["stat_queue_summary"] = qs.get("summary")
        row["stat_queue_ready"] = bool(qs.get("ready_now"))


def readiness_cache_age_sec(account_name: str) -> float | None:
    name = account_name.strip().lower()
    entry = _READINESS_CACHE.get(name)
    if not entry:
        return None
    return time.time() - entry[0]


def is_readiness_cache_fresh(account_name: str) -> bool:
    age = readiness_cache_age_sec(account_name)
    return age is not None and age < READINESS_CACHE_SEC


def enrich_snapshot_row(
    acc: Account,
    row: dict,
    *,
    api_delay: float = 0.08,
    network: bool = True,
) -> dict:
    """Readiness alanları — önce bellek cache; network=False ise ek API yok."""
    name = acc.name.strip().lower()
    now = time.time()
    cached = _READINESS_CACHE.get(name)
    if cached and now - cached[0] < READINESS_CACHE_SEC:
        row.update(cached[1])
        _apply_stat_queue(row, acc)
        return row

    if not network:
        _apply_stat_queue(row, acc)
        return row

    probes = probe_readiness_light(acc.token, acc.name, row, api_delay=api_delay, acc=acc)
    fields = readiness_fields(build_readiness_from_probes(probes))
    _READINESS_CACHE[name] = (now, dict(fields))
    row.update(fields)
    _apply_stat_queue(row, acc)
    row["readiness_fetched_at"] = now
    row["fetched_at"] = now
    return row


def skills_from_profile_player(player: dict) -> dict:
    skills = player.get("skills") or {}
    return skills if isinstance(skills, dict) else {}
