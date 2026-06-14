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
