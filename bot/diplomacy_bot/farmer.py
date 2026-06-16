from __future__ import annotations

from dataclasses import dataclass

from . import game_api
from .account_config import get_config
from .modules.orchestrator import TickResult, tick_account


@dataclass
class FarmResult:
    account_name: str
    username: str
    ok: bool
    balance_before: int
    balance_after: int
    earned_money: int
    earned_xp: int
    earned_diamonds: int
    error: str | None = None
    factory_id: str | None = None
    actions: list | None = None


def _tick_to_farm(t: TickResult) -> FarmResult:
    return FarmResult(
        account_name=t.account_name,
        username=t.username,
        ok=t.ok,
        balance_before=t.balance_before,
        balance_after=t.balance_after,
        earned_money=t.earned_money,
        earned_xp=t.earned_xp,
        earned_diamonds=t.earned_diamonds,
        error=t.error,
        factory_id=t.factory_id,
        actions=t.actions,
    )


def run_quick_farm(token: str, account_name: str, proxy_url: str | None = None, proxy_id: str = "") -> FarmResult:
    """Tek work döngüsü + stat otomasyonu — çağıran `interactive_account_context` içinde olmalı."""
    from .modules import factory, stats

    cfg = get_config(account_name)
    actions: list[dict] = []
    try:
        prof = game_api.get_profile(token)
        balance_before = prof.balance
        username = prof.username
    except Exception as e:
        return FarmResult(
            account_name=account_name,
            username="?",
            ok=False,
            balance_before=0,
            balance_after=0,
            earned_money=0,
            earned_xp=0,
            earned_diamonds=0,
            error=str(e)[:200],
        )

    if cfg.stat_auto_enabled:
        pre = stats.run_stat_automation(token, cfg)
        if pre.get("passive") or pre.get("upgrades"):
            actions.append({"stat_auto_pre": pre})

    from .modules import premium as premium_mod

    skip_work, skip_reason = premium_mod.should_skip_manual_work(token, cfg)
    if skip_work:
        actions.append({"skipped": skip_reason})
        try:
            after = game_api.get_profile(token, fresh=True)
            balance_after = after.balance
        except Exception:
            balance_after = balance_before
        if cfg.stat_auto_enabled:
            post = stats.run_stat_automation(token, cfg)
            if post.get("passive") or post.get("upgrades"):
                actions.append({"stat_auto_post": post})
        return FarmResult(
            account_name=account_name,
            username=username,
            ok=True,
            balance_before=balance_before,
            balance_after=balance_after,
            earned_money=0,
            earned_xp=0,
            earned_diamonds=0,
            error=None,
            factory_id=None,
            actions=actions or None,
        )

    work = factory.run_work_cycle(token, cfg)
    earned = work.get("earned") or {}
    money = int(earned.get("money") or 0)
    xp = int(earned.get("xp") or 0)
    diamonds = int(earned.get("diamonds") or 0)
    ok = bool(work.get("ok"))
    balance_after = balance_before + money if ok else balance_before
    if ok:
        try:
            after = game_api.get_profile(token, fresh=True)
            balance_after = after.balance
        except Exception:
            pass
        if cfg.stat_auto_enabled:
            post = stats.run_stat_automation(token, cfg)
            if post.get("passive") or post.get("upgrades"):
                actions.append({"stat_auto_post": post})
    err_msg = None
    if not ok:
        from .user_errors import format_work_error

        err_msg = format_work_error(work.get("error"), cooldown_ms=work.get("cooldown_ms"))
    return FarmResult(
        account_name=account_name,
        username=username,
        ok=ok,
        balance_before=balance_before,
        balance_after=balance_after,
        earned_money=money,
        earned_xp=xp,
        earned_diamonds=diamonds,
        error=err_msg or work.get("error"),
        factory_id=work.get("factory_id"),
        actions=actions or None,
    )


def run_farm(token: str, account_name: str, cycles: int = 1, proxy_url: str | None = None, proxy_id: str = "") -> FarmResult:
    from .account_pool import prepare_egress
    from .stealth_client import reset_request_proxy, set_request_proxy

    if proxy_id:
        prepare_egress(proxy_id)
    tok = set_request_proxy(proxy_url)
    try:
        cfg = get_config(account_name)
        last: TickResult | None = None
        for _ in range(max(1, cycles)):
            last = tick_account(token, account_name, cfg=cfg)
            if not last.ok and last.error and "cooldown" in (last.error or "").lower():
                break
            if not last.ok and last.earned_money <= 0:
                break
        assert last is not None
        return _tick_to_farm(last)
    finally:
        reset_request_proxy(tok)


def format_farm_result(r: FarmResult) -> str:
    if r.error and r.earned_money <= 0 and not r.ok:
        if r.error.startswith(("⏳", "❤️", "💊", "🏭", "🧳")):
            fab = f"\n🏭 `{r.factory_id}`" if r.factory_id else ""
            return f"{r.error}{fab}"
        hint = ""
        err = (r.error or "").lower()
        if "bekleme" in err or "cooldown" in err:
            hint = "\n💡 Hap/work cooldown — sonra tekrar dene"
        elif "bölge" in err or "eyalet" in err or "seyahat" in err:
            hint = "\n💡 `/setfabric <uuid>` ile hedef fabrika veya seyahat et"
        elif "can" in err or "sağlık" in err or "health" in err:
            hint = "\n💡 Hap craft/kullan sonra tekrar farm"
        elif "fabrika" in err:
            hint = "\n💡 `/setfabric` veya `work_mode foreign` ayarla"
        fab = f"\n🏭 fabrika: `{r.factory_id}`" if r.factory_id else ""
        return f"❌ {r.account_name} ({r.username}): {r.error}{fab}{hint}"
    extra = ""
    if r.factory_id:
        extra = f"\n🏭 `{r.factory_id}`"
    if r.earned_diamonds:
        extra += f" | +{r.earned_diamonds} 💎"
    return (
        f"✅ {r.account_name} ({r.username})\n"
        f"   +{r.earned_money:,} altın | +{r.earned_xp} XP{extra}\n"
        f"   {r.balance_before:,} → {r.balance_after:,}"
    )
