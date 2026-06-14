from __future__ import annotations

from typing import Any, Callable

from ..account_config import AccountConfig
from ..game_api import api as default_api

ApiFn = Callable[..., tuple[int, Any]]


def get_my_country_wars(token: str, *, _api: ApiFn = default_api) -> list[dict]:
    st, data = _api("GET", "/wars/my-country", token, delay=0.2)
    if st != 200:
        return []
    wars = data.get("wars") if isinstance(data, dict) else []
    return wars or []


def pick_war(cfg: AccountConfig, wars: list[dict]) -> dict | None:
    if not wars:
        return None
    if cfg.target_war_id:
        for w in wars:
            if str(w.get("id")) == cfg.target_war_id:
                return w
    return wars[0]


def contribute(token: str, war_id: str, side: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", f"/wars/{war_id}/contribute", token, {"side": side}, delay=0.3)
    return {"ok": st in (200, 201), "status": st, "side": side, "data": data}


def try_contribute(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> dict | None:
    if not cfg.war_enabled:
        return None
    wars = get_my_country_wars(token, _api=_api)
    war = pick_war(cfg, wars)
    if not war:
        return {"skipped": "no_active_war"}
    war_id = str(war.get("id"))
    side = cfg.contribute_side
    if side == "auto":
        side = war.get("my_side") or "attacker"
    return contribute(token, war_id, side, _api=_api)
