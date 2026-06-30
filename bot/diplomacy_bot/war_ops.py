from __future__ import annotations

from typing import Any, Callable

from .account_config import AccountConfig, get_config, normalize_role
from .game_api import api as default_api, get_profile
from .modules import economy, military, travel, war
from .war_board import detect_player_side
from .war_resolver import fetch_all_wars, resolve_war_from_reference, parse_war_reference

ApiFn = Callable[..., tuple[int, Any]]


def _resolve_side(war: dict, cfg: AccountConfig, player_country: str | None) -> str:
    side = cfg.contribute_side
    if side in ("attacker", "defender"):
        return side
    detected = detect_player_side(war, player_country)
    if detected in ("attacker", "defender"):
        return detected
    return str(war.get("my_side") or "attacker")


def _find_war(cfg: AccountConfig, token: str, war_id: str | None, *, _api: ApiFn) -> dict | None:
    if war_id:
        for w in war.get_all_wars(token, _api=_api):
            if str(w.get("id")) == str(war_id):
                return w
        return None
    wars = war.get_my_country_wars(token, _api=_api)
    picked = war.pick_war(cfg, wars)
    if picked:
        return picked
    if cfg.target_war_id:
        for w in war.get_all_wars(token, _api=_api):
            if str(w.get("id")) == cfg.target_war_id:
                return w
    return None


def _prewar_prep(token: str, cfg: AccountConfig, *, _api: ApiFn) -> list[dict]:
    """Hap + asker — max intensity profili."""
    actions: list[dict] = []
    if cfg.war_intensity == "max" or normalize_role(cfg.role) in ("war", "hybrid"):
        from .health_sync import work_health

        status = economy.get_auto_status(token, _api=_api)
        health = work_health(token, _api=_api, auto_status=status)
        if health < 100 and int(status.get("pill_cooldown_ms") or 0) <= 0:
            pills = economy.use_pills(token, _api=_api)
            if pills.get("ok"):
                actions.append({"use_pills": pills})
        mil = military.ensure_units_for_war(token, cfg, _api=_api)
        if mil and not mil.get("skipped") == "units_ok":
            actions.append({"military": mil})
    return actions


def run_war_contribute(
    token: str,
    account_name: str,
    *,
    war_id: str | None = None,
    side: str | None = None,
    _api: ApiFn = default_api,
) -> dict[str, Any]:
    """Tam savaş katkı pipeline — cooldown, seyahat, hap, asker, katkı."""
    cfg = get_config(account_name)
    role = normalize_role(cfg.role)
    if role not in ("war", "hybrid") and not cfg.war_enabled:
        return {"ok": False, "error": "Savaş katkısı kapalı — war/hybrid rolü veya war_enabled gerekli"}

    if travel.is_traveling(token, _api=_api):
        ts = travel.get_travel_status(token, _api=_api)
        return {
            "ok": False,
            "skipped": "traveling",
            "remaining_ms": ts.remaining_ms if ts else None,
            "error": "Seyahat halindesin — varınca tekrar dene",
        }

    ready, wait_ms = war.war_contribute_ready(token, _api=_api)
    if not ready:
        return {
            "ok": False,
            "skipped": "war_cooldown",
            "cooldown_ms": wait_ms,
            "error": f"Savaş katkısı beklemede ({wait_ms // 1000}s)",
        }

    target = _find_war(cfg, token, war_id, _api=_api)
    if not target:
        return {"ok": False, "skipped": "no_target_war", "error": "Hedef savaş bulunamadı"}

    target_id = str(target.get("id"))
    try:
        prof = get_profile(token)
        player_country = prof.country_name
    except Exception:
        player_country = None

    chosen_side = side if side in ("attacker", "defender") else _resolve_side(target, cfg, player_country)
    prep = _prewar_prep(token, cfg, _api=_api)

    result = war.contribute(token, target_id, chosen_side, _api=_api)
    out: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "result": result,
        "war_id": target_id,
        "side": chosen_side,
        "prep": prep,
        "war": target,
    }
    if not result.get("ok"):
        err = (result.get("data") or {}).get("error") or (result.get("data") or {}).get("message")
        out["error"] = err or "Katkı başarısız"
    return out


def resolve_war_by_text(token: str, text: str, *, _api: ApiFn = default_api) -> dict[str, Any]:
    ref = parse_war_reference(text)
    wars = fetch_all_wars(token, _api=_api)
    war_obj = resolve_war_from_reference(wars, ref)
    if war_obj is None:
        return {"ok": False, "error": "savaş bulunamadı", "war_count": len(wars)}
    if war_obj.get("_ambiguous"):
        return {"ok": False, "ambiguous": True, "matches": war_obj.get("matches")}
    return {"ok": True, "war": war_obj, "war_id": str(war_obj.get("id"))}
