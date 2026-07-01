from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from ..game_api import api as default_api, get_profile, invalidate_profile_cache

ApiFn = Callable[..., tuple[int, Any]]


@dataclass
class TravelStatus:
    traveling: bool
    arrived: bool
    province_name: str | None
    destination: str | None
    origin: str | None
    returning: bool
    remaining_ms: int
    total_ms: int
    raw: dict


def _parse_status(data: dict) -> TravelStatus:
    data = data or {}
    remaining = int(data.get("remaining_ms") or 0)
    traveling = bool(data.get("traveling") or data.get("in_transit"))
    arrived = bool(data.get("arrived"))
    if not traveling and not arrived and remaining > 0:
        traveling = True
    return TravelStatus(
        traveling=traveling,
        arrived=arrived or (not traveling and remaining <= 0),
        province_name=data.get("province_name"),
        destination=data.get("travel_destination"),
        origin=data.get("travel_origin"),
        returning=bool(data.get("travel_returning")),
        remaining_ms=remaining,
        total_ms=int(data.get("travel_total_ms") or 0),
        raw=data,
    )


def get_travel_status(token: str, *, _api: ApiFn = default_api) -> TravelStatus | None:
    st, data = _api("GET", "/provinces/travel/status", token, delay=0.2)
    if st != 200 or not isinstance(data, dict):
        return None
    return _parse_status(data)


def is_traveling(token: str, *, _api: ApiFn = default_api) -> bool:
    ts = get_travel_status(token, _api=_api)
    return bool(ts and ts.traveling and not ts.arrived)


def list_provinces(token: str, *, _api: ApiFn = default_api) -> list[dict]:
    st, data = _api("GET", "/provinces/all", token, delay=0.3)
    if st != 200:
        return []
    if isinstance(data, dict):
        return data.get("provinces") or data.get("data") or []
    return []


def _norm_province(name: str | None) -> str:
    return (name or "").strip().lower()


def find_province_by_name(provinces: list[dict], query: str) -> dict | None:
    q = _norm_province(query)
    if not q:
        return None
    for p in provinces:
        if _norm_province(p.get("name")) == q:
            return p
    for p in provinces:
        n = _norm_province(p.get("name"))
        if q in n or n in q:
            return p
    return None


def find_provinces_by_country(provinces: list[dict], country_query: str) -> list[dict]:
    q = country_query.strip().lower()
    if not q:
        return []
    out: list[dict] = []
    for p in provinces:
        cn = (p.get("country_name") or "").lower()
        cid = str(p.get("country_id") or "")
        if q in cn or cn in q or q == cid.lower():
            out.append(p)
    return out


def _travel_body(province_name: str, province_id: object | None = None) -> dict:
    body: dict[str, object] = {"province_name": province_name}
    if province_id is not None:
        body["province_id"] = province_id
    return body


def start_travel(token: str, province_name: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api(
        "POST",
        "/provinces/travel/start",
        token,
        _travel_body(province_name),
        delay=0.3,
    )
    body = data if isinstance(data, dict) else {"raw": str(data)[:200]}
    if st not in (200, 201):
        found = find_province_by_name(list_provinces(token, _api=_api), province_name)
        pid = (found or {}).get("id") or (found or {}).get("province_id")
        if pid is not None:
            st2, data2 = _api(
                "POST",
                "/provinces/travel/start",
                token,
                _travel_body(province_name, pid),
                delay=0.3,
            )
            body2 = data2 if isinstance(data2, dict) else {"raw": str(data2)[:200]}
            if st2 in (200, 201):
                return {"ok": True, "status": st2, "province_name": province_name, "data": body2}
            st, body = st2, body2
    return {"ok": st in (200, 201), "status": st, "province_name": province_name, "data": body}


def cancel_travel(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", "/provinces/travel/cancel", token, {}, delay=0.3)
    body = data if isinstance(data, dict) else {}
    return {"ok": st in (200, 201), "status": st, "data": body}


def skip_first_travel(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", "/provinces/travel/skip-first", token, {}, delay=0.3)
    body = data if isinstance(data, dict) else {}
    return {"ok": st in (200, 201), "status": st, "data": body}


def wait_for_arrival(
    token: str,
    *,
    timeout_ms: int = 600_000,
    poll_ms: int = 5_000,
    _api: ApiFn = default_api,
) -> TravelStatus | None:
    """Blocking poll — test ve tek seferlik komutlar için."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        ts = get_travel_status(token, _api=_api)
        if ts is None:
            return None
        if ts.arrived or not ts.traveling:
            invalidate_profile_cache(token)
            return ts
        time.sleep(min(poll_ms / 1000.0, max(0.5, deadline - time.monotonic())))
    return get_travel_status(token, _api=_api)


def ensure_in_province(
    token: str,
    target_province: str,
    *,
    leave_factory_first: bool = True,
    _api: ApiFn = default_api,
) -> dict:
    """Hedef eyalette değilse seyahat başlat (async tick'ler poll eder)."""
    target = target_province.strip()
    if not target:
        return {"ok": False, "error": "hedef eyalet boş"}

    try:
        prof = get_profile(token, fresh=True)
        if _norm_province(prof.province_name) == _norm_province(target):
            return {"ok": True, "skipped": "already_there", "province": prof.province_name}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    ts = get_travel_status(token, _api=_api)
    if ts and ts.traveling:
        if _norm_province(ts.destination) == _norm_province(target):
            return {
                "ok": True,
                "traveling": True,
                "remaining_ms": ts.remaining_ms,
                "destination": ts.destination,
            }
        cancel_travel(token, _api=_api)

    if leave_factory_first:
        _, ws = _api("GET", "/factories/work-status", token, delay=0.15)
        if isinstance(ws, dict) and ws.get("working"):
            _api("POST", "/factories/leave", token, {}, delay=0.15)

    started = start_travel(token, target, _api=_api)
    if not started["ok"]:
        err = (started.get("data") or {}).get("error") or (started.get("data") or {}).get("message")
        return {"ok": False, "error": err or f"seyahat başlatılamadı HTTP {started.get('status')}"}

    ts2 = get_travel_status(token, _api=_api)
    return {
        "ok": True,
        "started": True,
        "traveling": True,
        "destination": target,
        "remaining_ms": ts2.remaining_ms if ts2 else None,
    }


def travel_to_war_province(
    token: str,
    war: dict,
    side: str,
    *,
    _api: ApiFn = default_api,
) -> dict:
    side = (side or "attacker").lower()
    if side == "defender":
        prov = war.get("defender_province") or war.get("defender_name")
    else:
        prov = war.get("attacker_province") or war.get("attacker_name")
    if not prov:
        return {"ok": False, "error": "savaş eyaleti bulunamadı"}
    return ensure_in_province(token, str(prov), _api=_api)
