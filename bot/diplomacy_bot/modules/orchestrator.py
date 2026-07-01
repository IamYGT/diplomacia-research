from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..account_config import AccountConfig, get_config, normalize_role
from ..game_api import get_profile
from . import economy, factory, premium, stats, training, travel, war

ApiFn = economy.ApiFn
log = logging.getLogger(__name__)


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

    if travel.is_traveling(token, _api=api_fn):
        ts = travel.get_travel_status(token, _api=api_fn)
        result.error = "seyahat halindesin — bekle"
        if ts:
            result.actions.append({"travel": {"remaining_ms": ts.remaining_ms, "destination": ts.destination}})
        _persist_runtime_state(account_name, result)
        return result

    try:
        prof = get_profile(token)
    except Exception as e:
        result.error = str(e)
        return result

    result.username = prof.username
    result.balance_before = prof.balance

    # 0. Günlük ödül + görev claim (idempotent)
    routine = {}
    try:
        from ..routine_claims import run_routine_claims

        routine = run_routine_claims(token, cfg, _api=api_fn)
        if routine.get("daily"):
            result.actions.append({"routine_daily": routine["daily"]})
        if routine.get("quests") and routine["quests"].get("claimed_count"):
            result.actions.append({"routine_quests": routine["quests"]})
    except Exception as e:
        log.debug("routine_claims %s: %s", account_name, e)

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

    # 3. Savaş öncesi hazırlık (hap + can)
    if role in ("war", "hybrid") and cfg.war_enabled:
        craft_pre = economy.ensure_pills(token, cfg, _api=api_fn)
        if craft_pre:
            result.actions.append({"economy_pre": craft_pre})
        try:
            from ..health_sync import work_health

            status_pre = economy.get_auto_status(token, _api=api_fn)
            health_pre = work_health(token, _api=api_fn, auto_status=status_pre)
            if health_pre < 100 and int(status_pre.get("pill_cooldown_ms") or 0) <= 0:
                pills_pre = economy.use_pills(token, _api=api_fn)
                if pills_pre.get("ok"):
                    result.actions.append({"use_pills_pre": pills_pre})
        except Exception:
            pass

    # 4. Antrenman
    if cfg.training_enabled and role in ("farm", "war", "hybrid"):
        tr = training.try_free_attack(token, cfg, _api=api_fn)
        if tr:
            result.actions.append({"training": tr})

    # 5. Savaş (savaş + karma)
    if role in ("war", "hybrid") and cfg.war_enabled:
        wr = war.try_contribute(token, cfg, _api=api_fn)
        if wr:
            result.actions.append({"war": wr})

    # 6–7. Farm döngüsü (farm + karma) — premium auto/work açıksa sunucu yapar
    if role in ("farm", "hybrid"):
        craft = economy.ensure_pills(token, cfg, _api=api_fn)
        if craft:
            result.actions.append({"economy": craft})

        if skip_work:
            skip_action: dict = {"skipped": skip_reason}
            if skip_reason == "premium_auto_work":
                from ..health_sync import work_health

                status_pre = economy.get_auto_status(token, _api=api_fn)
                skip_action["health"] = work_health(token, _api=api_fn, auto_status=status_pre)
                skip_action["pill_cooldown_ms"] = int(status_pre.get("pill_cooldown_ms") or 0)
            result.actions.append(skip_action)
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
            if work.get("used_pills"):
                result.actions.append({"use_pills_pre": {"ok": True, "source": "farm"}})
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
                if work.get("used_pills") or craft:
                    result.ok = True
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

    state = "idle"
    if result.error:
        err = result.error.lower()
        if "travel" in err or "seyahat" in err:
            state = "traveling"
        elif "cooldown" in err or "bekle" in err:
            state = "cooldown"
        elif result.error == "paused":
            state = "off"
    else:
        for action in result.actions:
            if not isinstance(action, dict):
                continue
            if action.get("cooldown_ms"):
                state = "cooldown"
                break
            war_act = action.get("war") or {}
            if isinstance(war_act, dict) and war_act.get("skipped") == "war_cooldown":
                state = "cooldown"
                break
        else:
            if result.ok and result.earned_money > 0:
                state = "working"
    set_runtime_state(account_name, state)
    from ..tick_activity import record_tick_result

    record_tick_result(account_name, result)
