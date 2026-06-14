from __future__ import annotations

from typing import Any, Callable

from ..account_config import AccountConfig
from ..game_api import api as default_api
from .economy import get_auto_status

ApiFn = Callable[..., tuple[int, Any]]


def get_my_training_war(token: str, *, _api: ApiFn = default_api) -> dict | None:
    st, data = _api("GET", "/training-wars/my", token, delay=0.2)
    if st == 404:
        return None
    if st != 200:
        return None
    return data if isinstance(data, dict) else None


def attack_training(token: str, war_id: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("POST", f"/training-wars/{war_id}/attack", token, {}, delay=0.3)
    return {"ok": st in (200, 201), "status": st, "data": data}


def try_free_attack(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> dict | None:
    if not cfg.training_enabled:
        return None
    status = get_auto_status(token, _api=_api)
    if not status.get("free_attack_available"):
        return {"skipped": "free_attack_cooldown", "ms": status.get("free_attack_cooldown_ms")}
    war = get_my_training_war(token, _api=_api)
    if not war:
        return {"skipped": "no_training_war"}
    war_id = war.get("id") or war.get("war_id")
    if not war_id:
        return {"skipped": "no_training_war_id"}
    return attack_training(token, str(war_id), _api=_api)
