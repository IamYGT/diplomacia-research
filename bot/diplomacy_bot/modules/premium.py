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


def toggle_auto(token: str, mode: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", "/auto/toggle", token, {"mode": mode}, delay=0.3)
    return {"ok": st in (200, 201), "status": st, "mode": mode, "data": data}


def sync_premium_modes(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> list[dict]:
    """Hub hesapta auto/work + auto/war açık tut (premium gerekli)."""
    results: list[dict] = []
    hub = cfg.is_premium_hub or is_premium(token, _api=_api)
    if not hub:
        return results
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
