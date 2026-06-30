from __future__ import annotations

from dataclasses import dataclass, field

from typing import Iterable

from .account_config import AccountConfig, get_config, normalize_role, role_label
from .account_pool import load_rules
from .account_runtime import account_context
from .game_api import get_profile
from .store import Account, get_account, list_accounts, update_after_farm
from .modules.orchestrator import TickResult


@dataclass
class FleetRow:
    name: str
    username: str
    role: str
    role_label: str
    autofarm: bool
    proxy_id: str
    balance: int
    level: int = 0
    health: int = -1
    status: str = "ok"


@dataclass
class FleetRunResult:
    total: int = 0
    ok: int = 0
    skipped: int = 0
    errors: int = 0
    lines: list[str] = field(default_factory=list)
    results: list[TickResult] = field(default_factory=list)


def fleet_rows(*, live: bool = False, accounts: list[Account] | None = None) -> list[FleetRow]:
    """Hesap filosu özeti — live=True API çağırır (yavaş)."""
    rows: list[FleetRow] = []
    source = accounts if accounts is not None else list_accounts()
    for acc in source:
        cfg = get_config(acc.name)
        role = normalize_role(cfg.role)
        row = FleetRow(
            name=acc.name,
            username=acc.username or acc.name,
            role=role,
            role_label=role_label(role),
            autofarm=acc.autofarm,
            proxy_id=acc.proxy_id or "direct",
            balance=acc.last_balance,
        )
        if live:
            try:
                with account_context(acc):
                    p = get_profile(acc.token)
                    row.username = p.username
                    row.balance = p.balance
                    row.level = p.level
                    row.health = p.health
            except Exception as e:
                row.status = str(e)[:60]
        rows.append(row)
    return rows


def accounts_for_role(
    role: str | None = None,
    *,
    autofarm_only: bool = False,
    accounts: list[Account] | None = None,
) -> list[Account]:
    want = normalize_role(role) if role else None
    out: list[Account] = []
    source = accounts if accounts is not None else list_accounts()
    for acc in source:
        if acc.status and acc.status not in ("active", ""):
            continue
        cfg = get_config(acc.name)
        r = normalize_role(cfg.role)
        if r == "off":
            continue
        if want and r != want:
            continue
        if autofarm_only and not acc.autofarm:
            continue
        out.append(acc)
    return out


def tick_one(acc: Account) -> TickResult:
    cfg = get_config(acc.name)
    if normalize_role(cfg.role) == "off":
        return TickResult(account_name=acc.name, error="paused")
    with account_context(acc, rotate_egress=True):
        from .modules.scheduler import schedule_account

        result = schedule_account(acc.token, acc.name, cfg=cfg)
    if result.balance_after:
        update_after_farm(acc.name, result.balance_after)
    return result


def tick_fleet(
    *,
    role: str | None = None,
    names: list[str] | None = None,
    autofarm_only: bool = False,
    accounts: list[Account] | None = None,
) -> FleetRunResult:
    """Sıralı filo tick — arka plan/autofarm; UI için fleet_live.run_fleet_parallel_live kullan."""
    rules = load_rules()
    if names:
        accs = [a for n in names if (a := get_account(n))]
    else:
        accs = accounts_for_role(role, autofarm_only=autofarm_only, accounts=accounts)

    run = FleetRunResult(total=len(accs))
    import time

    for i, acc in enumerate(accs):
        if i > 0:
            time.sleep(rules.stagger_farm_sec)
        try:
            r = tick_one(acc)
            run.results.append(r)
            cfg = get_config(acc.name)
            tag = role_label(cfg.role)
            if r.error == "paused":
                run.skipped += 1
                run.lines.append(f"⏸ {acc.name} — durdu")
            elif r.ok or r.earned_money > 0 or r.actions:
                run.ok += 1
                extra = f"+{r.earned_money:,}₺" if r.earned_money else "aksiyon"
                run.lines.append(f"✅ {acc.name} [{tag}] {extra}")
            else:
                run.errors += 1
                run.lines.append(f"⚠️ {acc.name} [{tag}] {r.error or 'iş yok'}")
        except Exception as e:
            run.errors += 1
            run.lines.append(f"❌ {acc.name}: {e}")
    return run


def format_fleet_summary(run: FleetRunResult) -> str:
    head = f"👥 Filo tick: {run.ok}/{run.total} başarılı"
    if run.skipped:
        head += f" · {run.skipped} atlandı"
    if run.errors:
        head += f" · {run.errors} uyarı"
    body = "\n".join(run.lines[:15])
    if len(run.lines) > 15:
        body += f"\n… +{len(run.lines) - 15} hesap"
    return f"{head}\n\n{body}" if body else head


def count_by_role(
    *,
    accounts: list[Account] | None = None,
    names: Iterable[str] | None = None,
) -> dict[str, int]:
    if accounts is not None:
        source = accounts
    elif names is not None:
        name_set = set(names)
        source = [a for a in list_accounts() if a.name in name_set]
    else:
        source = list_accounts()
    counts = {r: 0 for r in ("farm", "war", "hybrid", "hub", "off")}
    for acc in source:
        counts[normalize_role(get_config(acc.name).role)] += 1
    return counts
