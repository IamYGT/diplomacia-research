from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from telegram import Bot

from .account_config import get_config, normalize_role, role_label
from .account_runtime import interactive_account_context
from .farmer import FarmResult, run_quick_farm
from .fleet_manager import FleetRunResult, accounts_for_role, format_fleet_summary
from .modules.orchestrator import TickResult, tick_account
from .store import Account, update_after_farm

# API stealth delay ayrı; bu sadece hesapların *başlama* aralığı (proxy burst önleme)
FLEET_START_STAGGER_SEC = float(os.environ.get("FLEET_START_STAGGER_SEC", "0.35"))


def farm_to_tick(fr: FarmResult) -> TickResult:
    return TickResult(
        account_name=fr.account_name,
        username=fr.username,
        ok=fr.ok,
        balance_before=fr.balance_before,
        balance_after=fr.balance_after,
        earned_money=fr.earned_money,
        earned_xp=fr.earned_xp,
        earned_diamonds=fr.earned_diamonds,
        error=fr.error,
        factory_id=fr.factory_id,
        actions=list(fr.actions or []),
    )


def format_tick_line(acc: Account, r: TickResult) -> str:
    """Tek hesap — kullanıcıya verbose satır."""
    cfg = get_config(acc.name)
    tag = role_label(cfg.role)
    name = acc.name

    if r.error == "paused":
        return f"⏸ {name} [{tag}] — rol kapalı (off)"

    err_low = (r.error or "").lower()
    if err_low and not r.ok and r.earned_money <= 0:
        if r.error and r.error.startswith(("⏳", "❤️", "💊", "🏭", "🧳")):
            return f"{r.error} · {name}"
        if "cooldown" in err_low or "bekleme" in err_low:
            return f"⏳ {name} [{tag}] — {r.error}"
        return f"⚠️ {name} [{tag}] — {r.error}"

    if r.ok or r.earned_money > 0:
        bits = [f"✅ {name} [{tag}] +{r.earned_money:,}₺"]
        if r.earned_xp:
            bits.append(f"+{r.earned_xp} XP")
        if r.earned_diamonds:
            bits.append(f"+{r.earned_diamonds}💎")
        if r.actions:
            bits.append(f"· {len(r.actions)} aksiyon")
        bits.append(f"→ {r.balance_after:,}₺")
        return " ".join(bits)

    if r.actions:
        return f"✅ {name} [{tag}] — {len(r.actions)} aksiyon (farm yok)"

    return f"⚪ {name} [{tag}] — bugün iş yok"


def tick_one_interactive(acc: Account) -> TickResult:
    """UI filo tick — hızlı mod + interactive delay."""
    cfg = get_config(acc.name)
    role = normalize_role(cfg.role)
    if role == "off":
        return TickResult(account_name=acc.name, error="paused")

    with interactive_account_context(acc):
        if role == "farm":
            fr = run_quick_farm(acc.token, acc.name, acc.proxy_url or None, acc.proxy_id or "")
            r = farm_to_tick(fr)
        else:
            r = tick_account(acc.token, acc.name, cfg=cfg)
        if r.balance_after:
            update_after_farm(acc.name, r.balance_after)
        from .tick_activity import record_tick_result

        record_tick_result(acc.name, r)
        return r


def _live_header(accs: list[Account], done: int) -> str:
    return f"👥 Filo · {len(accs)} hesap · {done}/{len(accs)} bitti"


def _live_body(status: dict[str, str], accs: list[Account]) -> str:
    return "\n".join(status.get(a.name, f"⏳ {a.name} — …") for a in accs)


@dataclass
class FleetLiveState:
    accounts: list[Account]
    status: dict[str, str] = field(default_factory=dict)
    run: FleetRunResult = field(default_factory=FleetRunResult)

    def __post_init__(self) -> None:
        self.run.total = len(self.accounts)
        for a in self.accounts:
            self.status[a.name] = f"⏳ {a.name} — sırada…"

    def text(self) -> str:
        done = sum(
            1
            for a in self.accounts
            if not self.status[a.name].startswith(("⏳", "🔄"))
        )
        head = _live_header(self.accounts, done)
        body = _live_body(self.status, self.accounts)
        return f"{head}\n\n{body}"[:3900]

    def record(self, acc: Account, r: TickResult) -> None:
        self.run.results.append(r)
        line = format_tick_line(acc, r)
        self.status[acc.name] = line
        self.run.lines.append(line)
        if r.error == "paused":
            self.run.skipped += 1
        elif r.ok or r.earned_money > 0 or r.actions:
            self.run.ok += 1
        elif r.error:
            self.run.errors += 1
        else:
            self.run.skipped += 1


async def run_fleet_parallel_live(
    bot: Bot,
    chat_id: int,
    message_id: int,
    accounts: list[Account],
    *,
    start_stagger_sec: float | None = None,
) -> FleetRunResult:
    """Hesapları asenkron başlat; her adımı Telegram mesajında canlı göster."""
    stagger = FLEET_START_STAGGER_SEC if start_stagger_sec is None else start_stagger_sec
    state = FleetLiveState(accounts)
    lock = asyncio.Lock()

    if not accounts:
        return state.run

    async def _edit() -> None:
        try:
            await bot.edit_message_text(state.text(), chat_id=chat_id, message_id=message_id)
        except Exception:
            pass

    await _edit()

    async def _one(acc: Account, index: int) -> None:
        await asyncio.sleep(index * stagger)
        async with lock:
            state.status[acc.name] = f"🔄 {acc.name} — çalışıyor…"
        await _edit()

        try:
            r = await asyncio.to_thread(tick_one_interactive, acc)
        except Exception as e:
            r = TickResult(account_name=acc.name, error=str(e)[:120])

        async with lock:
            state.record(acc, r)
        await _edit()

    await asyncio.gather(*[_one(a, i) for i, a in enumerate(accounts)])
    return state.run


def resolve_fleet_accounts(
    role: str | None = None,
    *,
    accounts: list[Account] | None = None,
) -> list[Account]:
    if role:
        return accounts_for_role(role, accounts=accounts)
    return accounts_for_role(None, accounts=accounts)


def format_fleet_final(run: FleetRunResult) -> str:
    return format_fleet_summary(run)
