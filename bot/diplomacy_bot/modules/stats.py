from __future__ import annotations

from typing import Any, Callable

from ..account_config import CLASS_STAT_PRIORITY, AccountConfig, DEFAULT_STAT_PRIORITY
from ..game_api import api as default_api, get_profile

ApiFn = Callable[..., tuple[int, Any]]


def resolve_priority(cfg: AccountConfig, player_class: str | None, passive_keys: list[str]) -> list[str]:
    """Sınıf + mevcut pasif skill anahtarlarına göre harcama sırası."""
    base = list(cfg.stat_priority) if cfg.stat_priority != DEFAULT_STAT_PRIORITY else []
    if not base and player_class:
        base = list(CLASS_STAT_PRIORITY.get(player_class, DEFAULT_STAT_PRIORITY))
    if not base:
        base = list(DEFAULT_STAT_PRIORITY)
    # API'de açık olan pasifleri öne al
    ordered: list[str] = []
    for k in passive_keys:
        if k not in ordered:
            ordered.append(k)
    for k in base:
        if k not in ordered:
            ordered.append(k)
    return ordered


def get_passive_skills(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("GET", "/players/passive-skills", token, delay=0.2)
    if st != 200:
        return {}
    return data if isinstance(data, dict) else {}


def spend_passive(token: str, skill: str, points: int, *, _api: ApiFn = default_api) -> dict:
    st, data = _api(
        "POST",
        "/players/passive-skills/spend",
        token,
        {"skill": skill, "points": points},
        delay=0.3,
    )
    return {"ok": st in (200, 201), "status": st, "skill": skill, "points": points, "data": data}


def spend_available(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> list[dict]:
    """Öncelik listesine göre tüm pasif puanları harca."""
    results: list[dict] = []
    data = get_passive_skills(token, _api=_api)
    points = int(data.get("available_points") or 0)
    if points <= 0:
        return results
    passive = data.get("passive_skills") or {}
    passive_keys = list(passive.keys())
    try:
        prof = get_profile(token)
        player_class = prof.player_class
    except Exception:
        player_class = None
    priority = resolve_priority(cfg, player_class, passive_keys)
    for skill in priority:
        if points <= 0:
            break
        r = spend_passive(token, skill, points, _api=_api)
        results.append(r)
        if r["ok"]:
            points = 0
            break
        err = str((r.get("data") or {}).get("error") or "").lower()
        if "invalid" in err or "geçersiz" in err or "bulunamad" in err:
            continue
        break
    return results
