from __future__ import annotations

from typing import Any, Callable

from ..account_config import AccountConfig
from ..game_api import api as default_api, get_profile
from ..war_board import detect_player_side
from .economy import get_auto_status

ApiFn = Callable[..., tuple[int, Any]]


def war_contribute_ready(token: str, *, _api: ApiFn = default_api) -> tuple[bool, int]:
    """next_war_in_ms gate — katkı cooldown."""
    status = get_auto_status(token, _api=_api)
    wait_ms = int(status.get("next_war_in_ms") or 0)
    return wait_ms <= 0, wait_ms


def list_global_wars(token: str, *, _api: ApiFn = default_api) -> list[dict]:
    st, data = _api("GET", "/wars", token, delay=0.25)
    if st != 200 or not isinstance(data, dict):
        return []
    return data.get("wars") or []


def get_my_country_wars(token: str, *, _api: ApiFn = default_api) -> list[dict]:
    st, data = _api("GET", "/wars/my-country", token, delay=0.2)
    if st != 200:
        return []
    wars = data.get("wars") if isinstance(data, dict) else []
    return wars or []


def get_all_wars(token: str, *, _api: ApiFn = default_api) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for wars in (list_global_wars(token, _api=_api), get_my_country_wars(token, _api=_api)):
        for w in wars:
            wid = str(w.get("id") or "")
            if wid and wid not in seen:
                seen.add(wid)
                out.append(w)
    return out


def pick_war(cfg: AccountConfig, wars: list[dict]) -> dict | None:
    if not wars:
        return None
    if cfg.target_war_id:
        for w in wars:
            if str(w.get("id")) == cfg.target_war_id:
                return w
    return wars[0]


def resolve_contribute_side(
    war: dict,
    cfg: AccountConfig,
    player_country: str | None = None,
) -> str:
    side = cfg.contribute_side
    if side in ("attacker", "defender"):
        return side
    detected = detect_player_side(war, player_country)
    if detected in ("attacker", "defender"):
        return detected
    return str(war.get("my_side") or "attacker")


def contribute(token: str, war_id: str, side: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", f"/wars/{war_id}/contribute", token, {"side": side}, delay=0.3)
    body = data if isinstance(data, dict) else {"raw": str(data)[:200]}
    return {
        "ok": st in (200, 201),
        "status": st,
        "side": side,
        "data": body,
        "cooldown_ms": body.get("next_war_in_ms") or body.get("remaining_ms"),
    }


def try_contribute(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> dict | None:
    if not cfg.war_enabled:
        return None

    ready, wait_ms = war_contribute_ready(token, _api=_api)
    if not ready:
        return {"skipped": "war_cooldown", "cooldown_ms": wait_ms}

    wars = get_my_country_wars(token, _api=_api)
    war = pick_war(cfg, wars)
    if not war and cfg.target_war_id:
        for w in get_all_wars(token, _api=_api):
            if str(w.get("id")) == cfg.target_war_id:
                war = w
                break

    if not war:
        return {"skipped": "no_active_war"}

    war_id = str(war.get("id"))
    try:
        prof = get_profile(token)
        country = prof.country_name
    except Exception:
        country = None
    side = resolve_contribute_side(war, cfg, country)
    return contribute(token, war_id, side, _api=_api)
