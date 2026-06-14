from __future__ import annotations

from typing import Any, Callable

from ..account_config import AccountConfig
from ..game_api import api as default_api

ApiFn = Callable[..., tuple[int, Any]]

DIAMONDS_PER_WORK = 20


def get_auto_status(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("GET", "/auto/status", token, delay=0.2)
    if st != 200 or not isinstance(data, dict):
        return {}
    return data


def craft_pills(token: str, diamonds: int, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", "/auto/craft-pills", token, {"diamonds": diamonds}, delay=0.3)
    return {"ok": st in (200, 201), "status": st, "data": data}


def use_pills(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", "/auto/use-pills", token, {}, delay=0.3)
    return {
        "ok": st in (200, 201),
        "status": st,
        "error": (data or {}).get("error") or (data or {}).get("message"),
        "cooldown_ms": (data or {}).get("remaining_ms") or (data or {}).get("pill_cooldown_ms"),
        "data": data,
    }


def ensure_pills(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> dict | None:
    """Hap stoğu düşükse elmas craft. Hata varsa dict döner."""
    if not cfg.craft_pills_when_low:
        return None
    status = get_auto_status(token, _api=_api)
    pills = int(status.get("health_pills") or 0)
    if pills >= cfg.min_pill_stock:
        return None
    if int(status.get("pill_cooldown_ms") or 0) > 0:
        return {"skipped": "pill_cooldown", "cooldown_ms": status["pill_cooldown_ms"]}
    from ..game_api import get_profile

    prof = get_profile(token)
    batch = min(cfg.craft_diamond_batch, prof.diamonds)
    if batch <= 0:
        return {"skipped": "no_diamonds", "need": cfg.craft_diamond_batch}
    result = craft_pills(token, batch, _api=_api)
    if not result["ok"]:
        err = (result.get("data") or {}).get("error") or (result.get("data") or {}).get("message")
        return {"error": err or f"craft HTTP {result['status']}"}
    return {"crafted": batch, "data": result["data"]}


def work_ready(token: str, *, _api: ApiFn = default_api) -> tuple[bool, int]:
    status = get_auto_status(token, _api=_api)
    wait_ms = int(status.get("next_work_in_ms") or 0)
    return wait_ms <= 0, wait_ms
