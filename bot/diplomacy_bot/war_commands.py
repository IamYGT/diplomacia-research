from __future__ import annotations

from typing import Any, Callable

from .account_config import AccountConfig, get_config, update_config_field
from .game_api import api as default_api
from .war_resolver import format_side_choice_prompt, format_war_sides, resolve_war

ApiFn = Callable[..., tuple[int, Any]]


def resolve_and_configure_war(
    token: str,
    account_name: str,
    text: str,
    *,
    _api: ApiFn = default_api,
    side: str | None = None,
) -> dict[str, Any]:
    """URL veya metin → target_war_id + taraf bilgisi."""
    resolved = resolve_war(token, text, _api=_api)
    if not resolved.get("ok"):
        return resolved

    war = resolved["war"]
    war_id = resolved["war_id"]
    cfg = get_config(account_name)
    fields: dict[str, object] = {
        "target_war_id": war_id,
        "war_enabled": True,
    }
    if side in ("attacker", "defender"):
        fields["contribute_side"] = side
    elif cfg.contribute_side == "auto":
        fields["contribute_side"] = "auto"
    update_config_field(account_name, **fields)

    return {
        "ok": True,
        "war_id": war_id,
        "war": war,
        "summary": format_war_sides(war),
        "sides_prompt": format_side_choice_prompt(war),
        "configured_side": fields.get("contribute_side", cfg.contribute_side),
        "needs_side_choice": side not in ("attacker", "defender") and cfg.contribute_side == "auto",
    }
