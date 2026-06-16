from __future__ import annotations

from dataclasses import dataclass, field

from ..account_config import AccountConfig, get_config, normalize_role
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
    """Tek orchestrator tick — role göre farm / savaş / karma."""
    api_fn = _api or economy.default_api
    cfg = cfg or get_config(account_name)
    role = normalize_role(cfg.role)
    result = TickResult(account_name=account_name)

    if role == "off":
        result.error = "paused"
        return result

    try:
        prof = get_profile(token)
    except Exception as e:
        result.error = str(e)
        return result

    result.username = prof.username
    result.balance_before = prof.balance

    # 1. Stat otomasyonu (pasif puan + altın — farm öncesi)
    if cfg.stat_auto_enabled:
        stat_pre = stats.run_stat_automation(token, cfg, _api=api_fn)
        if stat_pre.get("passive"):
            result.actions.append({"passive_stats": stat_pre["passive"]})
        if stat_pre.get("upgrades"):
            result.actions.append({"stat_upgrades": stat_pre["upgrades"]})

    # 2. Premium — profil sorgusu + auto/work aç
    prem_state = premium.fetch_premium_state(token, _api=api_fn)
    if prem_state.get("is_premium"):
        prem = premium.sync_premium_modes(token, cfg, _api=api_fn)
        if prem:
            result.actions.append({"premium": prem, "premium_state": prem_state})
        if role == "hub":
            try:
                after = get_profile(token)
                result.balance_after = after.balance
            except Exception:
                result.balance_after = result.balance_before
            result.ok = bool(result.actions)
            return result

    skip_work, skip_reason = premium.should_skip_manual_work(token, cfg, _api=api_fn)

    # 3. Antrenman
    if cfg.training_enabled and role in ("farm", "war", "hybrid"):
        tr = training.try_free_attack(token, cfg, _api=api_fn)
        if tr:
            result.actions.append({"training": tr})

    # 4. Savaş (savaş + karma)
    if role in ("war", "hybrid") and cfg.war_enabled:
        wr = war.try_contribute(token, cfg, _api=api_fn)
        if wr:
            result.actions.append({"war": wr})

    # 5–6. Farm döngüsü (farm + karma) — premium auto/work açıksa sunucu yapar
    if role in ("farm", "hybrid"):
        craft = economy.ensure_pills(token, cfg, _api=api_fn)
        if craft:
            result.actions.append({"economy": craft})

        if skip_work:
            result.actions.append({"skipped": skip_reason})
            result.ok = True
            if cfg.stat_auto_enabled:
                stat_post = stats.run_stat_automation(token, cfg, _api=api_fn)
                if stat_post.get("passive"):
                    result.actions.append({"passive_stats_post": stat_post["passive"]})
                if stat_post.get("upgrades"):
                    result.actions.append({"stat_upgrades_post": stat_post["upgrades"]})
        else:
            work = factory.run_work_cycle(token, cfg, _api=api_fn)
            result.factory_id = work.get("factory_id")
            if work.get("ok"):
                e = work.get("earned") or {}
                result.earned_money = int(e.get("money") or 0)
                result.earned_xp = int(e.get("xp") or 0)
                result.earned_diamonds = int(e.get("diamonds") or 0)
                result.ok = True
                if cfg.stat_auto_enabled:
                    stat_post = stats.run_stat_automation(token, cfg, _api=api_fn)
                    if stat_post.get("passive"):
                        result.actions.append({"passive_stats_post": stat_post["passive"]})
                    if stat_post.get("upgrades"):
                        result.actions.append({"stat_upgrades_post": stat_post["upgrades"]})
            else:
                result.error = work.get("error")
                if work.get("cooldown_ms"):
                    result.actions.append({"cooldown_ms": work["cooldown_ms"]})
    elif role == "war":
        craft = economy.ensure_pills(token, cfg, _api=api_fn)
        if craft:
            result.actions.append({"economy": craft})
        result.ok = bool(result.actions) and any(
            a.get("war") for a in result.actions if isinstance(a, dict)
        )
        if not result.ok and result.actions:
            result.ok = True  # training/war attempt counts

    try:
        after = get_profile(token)
        result.balance_after = after.balance
    except Exception:
        result.balance_after = result.balance_before + result.earned_money

    if result.ok and result.earned_money == 0 and result.balance_after > result.balance_before:
        result.earned_money = result.balance_after - result.balance_before

    _persist_runtime_state(account_name, result)
    return result


def _persist_runtime_state(account_name: str, result: TickResult) -> None:
    from ..store import set_runtime_state

    if result.error:
        err = result.error.lower()
        if "travel" in err or "seyahat" in err:
            set_runtime_state(account_name, "traveling")
            return
        if "cooldown" in err or "bekle" in err:
            set_runtime_state(account_name, "cooldown")
            return
    for action in result.actions:
        if isinstance(action, dict) and action.get("cooldown_ms"):
            set_runtime_state(account_name, "cooldown")
            return
    if result.ok and result.earned_money > 0:
        set_runtime_state(account_name, "working")
    elif result.ok and result.actions:
        set_runtime_state(account_name, "idle")
    elif result.error == "paused":
        set_runtime_state(account_name, "off")
    else:
        set_runtime_state(account_name, "idle")
