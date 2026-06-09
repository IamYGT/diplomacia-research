from __future__ import annotations

from typing import Any, Callable

from .game_api import api, get_profile

ApiFn = Callable[..., tuple[int, Any]]


def factory_in_province(token: str, *, _api: ApiFn = api) -> str | None:
    prof = get_profile(token)
    province = prof.province_name
    _, fac = _api("GET", "/factories/my", token, delay=0.3)
    factories = fac.get("factories", [])
    if province:
        for f in factories:
            if f.get("province_name") == province:
                return f["id"]
    return factories[0]["id"] if factories else None


def ensure_factory(token: str, *, _api: ApiFn = api, build_name: str = "BotFarm") -> str | None:
    fid = factory_in_province(token, _api=_api)
    if fid:
        return fid
    st, built = _api("POST", "/factories/build", token, {"type": "elmas", "name": build_name})
    if st not in (200, 201):
        return None
    return (built.get("factory") or {}).get("id") or factory_in_province(token, _api=_api)


def prepare_join(token: str, factory_id: str, *, _api: ApiFn = api, build_suffix: str = "2") -> str:
    """leave → join; eyalet uyumsuzluğunda yerel fabrika kur."""
    _, ws = _api("GET", "/factories/work-status", token, delay=0.2)
    if ws.get("working"):
        _api("POST", "/factories/leave", token, {}, delay=0.3)
    factory_id = factory_in_province(token, _api=_api) or factory_id
    _, joined = _api("POST", "/factories/join", token, {"factory_id": factory_id}, delay=0.3)
    if joined.get("error") and "bölge" in str(joined.get("error")).lower():
        _api("POST", "/factories/leave", token, {}, delay=0.2)
        st, built = _api("POST", "/factories/build", token, {"type": "elmas", "name": f"BotFarm{build_suffix}"})
        if st in (200, 201):
            factory_id = (built.get("factory") or {}).get("id") or factory_id
            _api("POST", "/factories/join", token, {"factory_id": factory_id}, delay=0.3)
    return factory_id


def use_pills_if_needed(token: str, *, _api: ApiFn = api) -> dict | None:
    """Can < 100 ise hap kullan. Hata varsa dict döner, yoksa None."""
    prof = get_profile(token)
    if prof.health >= 100:
        return None
    st, pills = _api("POST", "/auto/use-pills", token, {}, delay=0.3)
    if st != 200:
        return {
            "error": pills.get("error") or pills.get("message") or "hap yok",
            "cooldown_ms": pills.get("remaining_ms"),
        }
    return None


def run_work_cycle(token: str, factory_id: str | None = None, *, _api: ApiFn = api) -> dict:
    """leave → join (eyalet) → pills → work."""
    result: dict[str, Any] = {"ok": False, "earned": {}, "error": None}
    factory_id = factory_id or ensure_factory(token, _api=_api)
    if not factory_id:
        result["error"] = "fabrika yok — eyalette fabrika kurulamadı"
        return result

    factory_id = prepare_join(token, factory_id, _api=_api)
    pill_err = use_pills_if_needed(token, _api=_api)
    if pill_err:
        result["error"] = pill_err["error"]
        result["cooldown_ms"] = pill_err.get("cooldown_ms")
        return result

    st, work = _api("POST", "/factories/work", token, {}, delay=0.3)
    earned = work.get("earned") or {}
    result["earned"] = earned
    result["ok"] = st == 200
    if not result["ok"]:
        result["error"] = work.get("error") or work.get("message") or f"work HTTP {st}"
    return result
