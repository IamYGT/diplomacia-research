from __future__ import annotations

from typing import Any, Callable

from ..account_config import AccountConfig
from ..game_api import api as default_api, get_profile
from .economy import get_auto_status

ApiFn = Callable[..., tuple[int, Any]]


def is_premium(token: str, *, _api: ApiFn = default_api) -> bool:
    try:
        return get_profile(token).is_premium
    except Exception:
        st, data = _api("GET", "/players/profile", token, delay=0.2)
        if st == 200 and isinstance(data, dict):
            return bool((data.get("player") or {}).get("is_premium"))
    return False


def premium_auto_work_active(token: str, *, _api: ApiFn = default_api) -> bool:
    """Sunucu tarafı premium auto/work açık mı?"""
    if not is_premium(token, _api=_api):
        return False
    status = get_auto_status(token, _api=_api)
    return bool(status.get("auto_work_active"))


def should_skip_manual_work(
    token: str,
    cfg: AccountConfig,
    *,
    _api: ApiFn = default_api,
) -> tuple[bool, str]:
    """Premium + auto/work → manuel farm / work döngüsü gereksiz."""
    if not is_premium(token, _api=_api):
        return False, ""
    status = get_auto_status(token, _api=_api)
    if status.get("auto_work_active"):
        return True, "premium_auto_work"
    return False, ""


def fetch_premium_state(token: str, *, _api: ApiFn = default_api) -> dict:
    """Profil + auto/status — panel ve orchestrator için."""
    state: dict = {
        "is_premium": False,
        "auto_work_active": False,
        "auto_war_active": False,
        "premium_until": None,
        "premium_days_left": None,
    }
    try:
        st, data = _api("GET", "/players/profile", token, delay=0.15)
        if st == 200 and isinstance(data, dict):
            p = data.get("player") or {}
            state["is_premium"] = bool(p.get("is_premium"))
            state["premium_until"] = p.get("premium_until")
            state["premium_days_left"] = p.get("premium_days_left")
    except Exception:
        pass
    try:
        status = get_auto_status(token, _api=_api)
        state["auto_work_active"] = bool(status.get("auto_work_active"))
        state["auto_war_active"] = bool(status.get("auto_war_active"))
    except Exception:
        pass
    return state


def toggle_auto(token: str, mode: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", "/auto/toggle", token, {"mode": mode}, delay=0.3)
    return {"ok": st in (200, 201), "status": st, "mode": mode, "data": data}


def sync_premium_modes(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> list[dict]:
    """Premium hesapta auto/work (+ isteğe bağlı auto/war) açık tut."""
    results: list[dict] = []
    if not is_premium(token, _api=_api):
        results.append({"skipped": "not_premium"})
        return results
    status = get_auto_status(token, _api=_api)
    if not status.get("auto_work_active"):
        tw = toggle_auto(token, "work", _api=_api)
        if not tw["ok"] and tw.get("status") == 403:
            tw["skipped"] = "wrong_province_for_auto_work"
        results.append(tw)
    if cfg.war_enabled and not status.get("auto_war_active"):
        results.append(toggle_auto(token, "war", _api=_api))
    return results
