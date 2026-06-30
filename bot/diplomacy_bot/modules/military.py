from __future__ import annotations

from typing import Any, Callable

from ..account_config import AccountConfig
from ..game_api import api as default_api

ApiFn = Callable[..., tuple[int, Any]]

DEFAULT_MIN_UNITS = 1


def fetch_military(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("GET", "/military/me", token, delay=0.2)
    if st != 200 or not isinstance(data, dict):
        return {"ok": False, "status": st, "data": data if isinstance(data, dict) else {}}
    return {"ok": True, "status": st, "data": data}


def unit_total(military_data: dict) -> int:
    units = military_data.get("units") or {}
    if isinstance(units, dict):
        return sum(int(v) for v in units.values() if isinstance(v, (int, float)))
    if isinstance(units, list):
        return sum(int(u.get("count") or 0) for u in units if isinstance(u, dict))
    return int(military_data.get("unit_total") or 0)


def train(token: str, count: int = 1, *, _api: ApiFn = default_api) -> dict:
    body: dict[str, Any] = {}
    if count > 0:
        body["count"] = count
    st, data = _api("POST", "/military/train", token, body or None, delay=0.3)
    payload = data if isinstance(data, dict) else {"raw": str(data)[:200]}
    return {
        "ok": st in (200, 201),
        "status": st,
        "data": payload,
        "error": payload.get("error") or payload.get("message"),
    }


def ensure_units_for_war(
    token: str,
    cfg: AccountConfig,
    *,
    min_units: int | None = None,
    _api: ApiFn = default_api,
) -> dict | None:
    """Savaş öncesi birim kontrolü — düşükse train dene."""
    if not cfg.war_enabled:
        return None
    threshold = min_units if min_units is not None else DEFAULT_MIN_UNITS
    mil = fetch_military(token, _api=_api)
    if not mil.get("ok"):
        return {"skipped": "military_fetch_failed", "detail": mil}
    total = unit_total(mil.get("data") or {})
    if total >= threshold:
        return {"skipped": "units_ok", "unit_total": total}
    trained = train(token, 1, _api=_api)
    return {"trained": trained, "unit_total_before": total}
