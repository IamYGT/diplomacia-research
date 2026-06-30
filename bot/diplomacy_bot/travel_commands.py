from __future__ import annotations

from typing import Any, Callable

from .game_api import api as default_api, get_profile
from .modules.travel import (
    cancel_travel,
    ensure_in_province,
    find_province_by_name,
    find_provinces_by_country,
    get_travel_status,
    list_provinces,
    start_travel,
)

ApiFn = Callable[..., tuple[int, Any]]


def format_travel_status(token: str, *, _api: ApiFn = default_api) -> str:
    ts = get_travel_status(token, _api=_api)
    if ts is None:
        return "❌ Seyahat durumu alınamadı"
    if ts.traveling and not ts.arrived:
        mins = max(0, ts.remaining_ms // 60_000)
        dest = ts.destination or "?"
        origin = ts.origin or ts.province_name or "?"
        ret = " (dönüş)" if ts.returning else ""
        return (
            f"🚶 Seyahat{ret}\n"
            f"📍 {origin} → {dest}\n"
            f"⏳ ~{mins} dk kaldı"
        )
    try:
        prof = get_profile(token)
        loc = prof.province_name or "?"
    except Exception:
        loc = ts.province_name or "?"
    return f"✅ Seyahat yok — şu an: {loc}"


def run_travel(
    token: str,
    destination: str,
    *,
    _api: ApiFn = default_api,
) -> dict[str, Any]:
    """Manuel seyahat — eyalet adı veya ülke araması."""
    dest = (destination or "").strip()
    if not dest:
        return {"ok": False, "error": "hedef boş"}

    if dest.lower() in ("durum", "status", "?"):
        return {"ok": True, "message": format_travel_status(token, _api=_api)}

    if dest.lower() in ("iptal", "cancel"):
        r = cancel_travel(token, _api=_api)
        return {"ok": r.get("ok"), "cancelled": True, "data": r}

    provinces = list_provinces(token, _api=_api)
    prov = find_province_by_name(provinces, dest) if provinces else None
    if not prov:
        matches = find_provinces_by_country(provinces, dest) if provinces else []
        if len(matches) == 1:
            prov = matches[0]
        elif len(matches) > 1:
            names = ", ".join(p.get("name") or "?" for p in matches[:8])
            return {
                "ok": False,
                "ambiguous": True,
                "provinces": matches,
                "error": f"Birden fazla eyalet: {names}",
            }

    target_name = (prov or {}).get("name") or dest
    return ensure_in_province(token, target_name, _api=_api)
