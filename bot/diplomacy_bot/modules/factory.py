from __future__ import annotations

from typing import Any, Callable

from ..account_config import AccountConfig
from ..game_api import api as default_api, get_profile
from .economy import work_ready

ApiFn = Callable[..., tuple[int, Any]]


def _score_factory(f: dict, province: str | None) -> float:
    """Yabancı fabrika seçimi — elmas, seviye, maaş oranı."""
    score = 0.0
    if f.get("type") == "elmas":
        score += 1000
    score += int(f.get("level") or 0) * 10
    score += int(f.get("salary_rate") or 0)
    if province and f.get("province_name") == province:
        score += 500
    return score


def factory_in_province(token: str, *, _api: ApiFn = default_api) -> str | None:
    prof = get_profile(token)
    province = prof.province_name
    _, fac = _api("GET", "/factories/my", token, delay=0.3)
    factories = fac.get("factories", [])
    if province:
        for f in factories:
            if f.get("province_name") == province:
                return f["id"]
    return None  # eyalette fabrika yok — yabancı moda düş


def list_region_factories(token: str, *, _api: ApiFn = default_api) -> list[dict]:
    st, data = _api("GET", "/factories/region?page=1&limit=20", token, delay=0.3)
    if st != 200:
        return []
    return data.get("factories") or []


def pick_foreign_factory(token: str, *, _api: ApiFn = default_api) -> str | None:
    prof = get_profile(token)
    factories = list_region_factories(token, _api=_api)
    if not factories:
        return None
    best = max(factories, key=lambda f: _score_factory(f, prof.province_name))
    return best.get("id")


def build_factory(token: str, name: str = "BotFarm", *, _api: ApiFn = default_api) -> str | None:
    st, built = _api("POST", "/factories/build", token, {"type": "elmas", "name": name}, delay=0.3)
    if st not in (200, 201):
        return None
    return (built.get("factory") or {}).get("id") or factory_in_province(token, _api=_api)


def is_traveling(token: str, *, _api: ApiFn = default_api) -> bool:
    st, data = _api("GET", "/provinces/travel/status", token, delay=0.2)
    if st != 200:
        return False
    return bool(data.get("traveling") or data.get("in_transit"))


def resolve_factory_id(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> tuple[str | None, str | None]:
    """UUID + hata mesajı."""
    mode = cfg.work_mode
    if mode == "fixed" and cfg.preferred_factory_id:
        return cfg.preferred_factory_id, None
    if mode == "foreign":
        fid = pick_foreign_factory(token, _api=_api)
        if fid:
            return fid, None
        return None, "eyalette uygun yabancı fabrika bulunamadı"
    if mode == "own":
        fid = factory_in_province(token, _api=_api)
        if fid:
            return fid, None
        # Eyalette kendi fabrika yok — bölgedeki açık fabrikaya düş
        foreign = pick_foreign_factory(token, _api=_api)
        if foreign:
            return foreign, None
        if cfg.allow_auto_build:
            built = build_factory(token, _api=_api)
            return built, None if built else "fabrika kurulamadı"
        return None, "eyalette fabrika yok — /setfabric foreign veya seyahat et"
    # auto — geri uyumluluk
    fid = factory_in_province(token, _api=_api)
    if fid:
        return fid, None
    if cfg.allow_auto_build:
        return build_factory(token, _api=_api), None
    return None, "fabrika yok ve auto_build kapalı"


def prepare_join(
    token: str,
    factory_id: str,
    cfg: AccountConfig,
    *,
    _api: ApiFn = default_api,
    build_suffix: str = "2",
) -> tuple[str, str | None]:
    """leave → join. Bölge hatasında sadece auto mod + allow_auto_build ile kur."""
    if is_traveling(token, _api=_api):
        return factory_id, "seyahat halindesin — bekle"

    _, ws = _api("GET", "/factories/work-status", token, delay=0.2)
    if ws.get("working"):
        _api("POST", "/factories/leave", token, {}, delay=0.3)

    if cfg.work_mode != "fixed":
        resolved, err = resolve_factory_id(token, cfg, _api=_api)
        if err:
            return factory_id, err
        if resolved:
            factory_id = resolved

    _, joined = _api("POST", "/factories/join", token, {"factory_id": factory_id}, delay=0.3)
    err_text = str((joined or {}).get("error") or (joined or {}).get("message") or "")
    if joined.get("error") and "bölge" in err_text.lower():
        _api("POST", "/factories/leave", token, {}, delay=0.2)
        if cfg.work_mode == "auto" or cfg.allow_auto_build:
            st, built = _api(
                "POST",
                "/factories/build",
                token,
                {"type": "elmas", "name": f"BotFarm{build_suffix}"},
                delay=0.3,
            )
            if st in (200, 201):
                factory_id = (built.get("factory") or {}).get("id") or factory_id
                _api("POST", "/factories/join", token, {"factory_id": factory_id}, delay=0.3)
                return factory_id, None
        return factory_id, "bölge uyumsuz — hedef fabrikaya seyahat et veya /setfabric"
    if joined.get("error"):
        return factory_id, err_text or "join başarısız"
    return factory_id, None


def use_pills_if_needed(token: str, *, _api: ApiFn = default_api) -> dict | None:
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


def run_work_cycle(
    token: str,
    cfg: AccountConfig,
    factory_id: str | None = None,
    *,
    _api: ApiFn = default_api,
) -> dict:
    result: dict[str, Any] = {"ok": False, "earned": {}, "error": None, "factory_id": factory_id}
    ready, wait_ms = work_ready(token, _api=_api)
    if not ready:
        result["error"] = "work cooldown"
        result["cooldown_ms"] = wait_ms
        return result

    fid, resolve_err = resolve_factory_id(token, cfg, _api=_api)
    if resolve_err:
        result["error"] = resolve_err
        return result
    factory_id = factory_id or fid
    if not factory_id:
        result["error"] = "fabrika seçilemedi"
        return result

    factory_id, join_err = prepare_join(token, factory_id, cfg, _api=_api)
    result["factory_id"] = factory_id
    if join_err:
        result["error"] = join_err
        return result

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
