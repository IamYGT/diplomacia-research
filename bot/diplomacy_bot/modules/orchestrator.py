from __future__ import annotations

from dataclasses import dataclass, field

from ..account_config import AccountConfig, get_config
from ..game_api import get_profile
from . import economy, factory, premium, stats, training, war

ApiFn = economy.ApiFn


@dataclass
class TickResult:
    account_name: str
    username: str = ""
    ok: bool = False
    balance_before: int = 0
    balance_after: int = 0
    earned_money: int = 0
    earned_xp: int = 0
    earned_diamonds: int = 0
    error: str | None = None
    factory_id: str | None = None
    actions: list[dict] = field(default_factory=list)


def tick_account(
    token: str,
    account_name: str,
    *,
    cfg: AccountConfig | None = None,
    _api: ApiFn | None = None,
) -> TickResult:
    """Tek orchestrator tick — stat → premium → training → war → economy → work."""
    api_fn = _api or economy.default_api
    cfg = cfg or get_config(account_name)
    result = TickResult(account_name=account_name)

    try:
        prof = get_profile(token)
    except Exception as e:
        result.error = str(e)
        return result

    result.username = prof.username
    result.balance_before = prof.balance

    # 1. Pasif stat
    stat_actions = stats.spend_available(token, cfg, _api=api_fn)
    if stat_actions:
        result.actions.append({"stats": stat_actions})

    # 2. Premium hub sync
    prem = premium.sync_premium_modes(token, cfg, _api=api_fn)
    if prem:
        result.actions.append({"premium": prem})

    # 3. Antrenman saldırısı
    tr = training.try_free_attack(token, cfg, _api=api_fn)
    if tr:
        result.actions.append({"training": tr})

    # 4. Savaş katkısı
    wr = war.try_contribute(token, cfg, _api=api_fn)
    if wr:
        result.actions.append({"war": wr})

    # 5. Hap craft
    craft = economy.ensure_pills(token, cfg, _api=api_fn)
    if craft:
        result.actions.append({"economy": craft})

    # 6. Fabrika work
    work = factory.run_work_cycle(token, cfg, _api=api_fn)
    result.factory_id = work.get("factory_id")
    if work.get("ok"):
        e = work.get("earned") or {}
        result.earned_money = int(e.get("money") or 0)
        result.earned_xp = int(e.get("xp") or 0)
        result.earned_diamonds = int(e.get("diamonds") or 0)
        result.ok = True
    else:
        result.error = work.get("error")
        if work.get("cooldown_ms"):
            result.actions.append({"cooldown_ms": work["cooldown_ms"]})

    try:
        after = get_profile(token)
        result.balance_after = after.balance
    except Exception:
        result.balance_after = result.balance_before + result.earned_money

    if result.ok and result.earned_money == 0 and result.balance_after > result.balance_before:
        result.earned_money = result.balance_after - result.balance_before

    return result
