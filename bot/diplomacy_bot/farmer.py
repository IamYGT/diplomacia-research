from __future__ import annotations

from dataclasses import dataclass

from . import game_api


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


def run_farm(token: str, account_name: str, cycles: int = 1) -> FarmResult:
    prof = game_api.get_profile(token)
    before = prof.balance
    total_money = 0
    total_xp = 0
    total_diamonds = 0
    last_error = None
    factory_id = game_api.ensure_factory(token)

    for _ in range(max(1, cycles)):
        r = game_api.farm_once(token, factory_id)
        if r.get("ok"):
            e = r.get("earned") or {}
            total_money += int(e.get("money") or 0)
            total_xp += int(e.get("xp") or 0)
            total_diamonds += int(e.get("diamonds") or 0)
        else:
            last_error = r.get("error")
            break

    after_prof = game_api.get_profile(token)
    return FarmResult(
        account_name=account_name,
        username=after_prof.username,
        ok=last_error is None and total_money > 0,
        balance_before=before,
        balance_after=after_prof.balance,
        earned_money=total_money or (after_prof.balance - before),
        earned_xp=total_xp,
        earned_diamonds=total_diamonds,
        error=last_error,
    )


def format_farm_result(r: FarmResult) -> str:
    if r.error and r.earned_money <= 0:
        hint = ""
        err = (r.error or "").lower()
        if "bekleme" in err or "cooldown" in err:
            hint = "\n💡 Hap cooldown ~10 dk — sonra `farm yap` veya `hap kullan`"
        elif "bölge" in err or "eyalet" in err:
            hint = "\n💡 Eyalet uyumsuzluğu — bot yeniden join denedi; `ne durumdayım` kontrol et"
        elif "can" in err or "sağlık" in err or "health" in err:
            hint = "\n💡 `hap kullan` sonra tekrar `farm yap`"
        return f"❌ {r.account_name} ({r.username}): {r.error}{hint}"
    return (
        f"✅ {r.account_name} ({r.username})\n"
        f"   +{r.earned_money:,} altın | +{r.earned_xp} XP | +{r.earned_diamonds} 💎\n"
        f"   {r.balance_before:,} → {r.balance_after:,}"
    )
