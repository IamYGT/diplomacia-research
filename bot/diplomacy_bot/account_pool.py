from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from .config import BOT_DIR, DATA_DIR


RULES_PATH = Path(os.environ.get("ACCOUNT_RULES_PATH", DATA_DIR / "accounts" / "rules.yaml"))


@dataclass
class ProxySlot:
    id: str
    url: str
    max_slots: int
    labels: list[str]
    rotate_tor: bool = False


@dataclass
class PoolRules:
    max_accounts_per_egress: int
    min_request_delay_sec: float
    farm_interval_sec: int
    max_concurrent_workers: int
    cooldown_on_429_sec: int
    stagger_farm_sec: int
    proxy_pool: list[ProxySlot]
    avoid_push_token: bool
    avoid_cross_transfer: bool


def _default_rules() -> PoolRules:
    return PoolRules(
        max_accounts_per_egress=2,
        min_request_delay_sec=6.0,
        farm_interval_sec=620,
        max_concurrent_workers=1,
        cooldown_on_429_sec=180,
        stagger_farm_sec=30,
        proxy_pool=[ProxySlot(id="direct", url="", max_slots=1, labels=["server-default"])],
        avoid_push_token=True,
        avoid_cross_transfer=True,
    )


def load_rules() -> PoolRules:
    if not RULES_PATH.exists() or yaml is None:
        return _default_rules()
    raw = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    limits = raw.get("limits") or {}
    signals = raw.get("signals_avoid") or {}
    schedule = raw.get("schedule") or {}
    pool: list[ProxySlot] = []
    for p in raw.get("proxy_pool") or []:
        pool.append(
            ProxySlot(
                id=str(p.get("id", "unknown")),
                url=str(p.get("url") or ""),
                max_slots=int(p.get("max_slots") or 1),
                labels=list(p.get("labels") or []),
                rotate_tor=bool(p.get("rotate_tor", False)),
            )
        )
    if not pool:
        pool = [ProxySlot(id="direct", url="", max_slots=1, labels=["server-default"])]
    return PoolRules(
        max_accounts_per_egress=int(limits.get("max_accounts_per_egress") or 2),
        min_request_delay_sec=float(limits.get("min_request_delay_sec") or 6),
        farm_interval_sec=int(limits.get("farm_interval_sec") or 620),
        max_concurrent_workers=int(limits.get("max_concurrent_workers") or 1),
        cooldown_on_429_sec=int(limits.get("cooldown_on_429_sec") or 180),
        stagger_farm_sec=int(schedule.get("stagger_farm_sec") or 30),
        proxy_pool=pool,
        avoid_push_token=bool(signals.get("push_token", True)),
        avoid_cross_transfer=bool(signals.get("cross_transfer", True)),
    )


def get_proxy_by_id(proxy_id: str) -> ProxySlot | None:
    for p in load_rules().proxy_pool:
        if p.id == proxy_id:
            return p
    return None


def count_on_proxy(proxy_id: str, assignments: dict[str, str]) -> int:
    return sum(1 for v in assignments.values() if v == proxy_id)


def suggest_proxy(assignments: dict[str, str]) -> ProxySlot:
    rules = load_rules()
    best: ProxySlot | None = None
    best_count = 10**9
    for p in rules.proxy_pool:
        n = count_on_proxy(p.id, assignments)
        if n < p.max_slots and n < rules.max_accounts_per_egress and n < best_count:
            best = p
            best_count = n
    return best or rules.proxy_pool[0]


def format_pool_status(assignments: dict[str, str]) -> str:
    rules = load_rules()
    lines = ["*Proxy pool*"]
    for p in rules.proxy_pool:
        n = count_on_proxy(p.id, assignments)
        cap = min(p.max_slots, rules.max_accounts_per_egress)
        mask = p.url[:20] + "…" if len(p.url) > 20 else (p.url or "(direct)")
        lines.append(f"• `{p.id}` {n}/{cap} — {mask} [{', '.join(p.labels)}]")
    lines.append(f"\nKural: max {rules.max_accounts_per_egress} hesap/egress, delay {rules.min_request_delay_sec}s")
    return "\n".join(lines)


def prepare_egress(proxy_id: str) -> None:
    """Tor slot ise NEWNYM ile exit IP yenile."""
    slot = get_proxy_by_id(proxy_id)
    if slot and slot.rotate_tor:
        from .tor_pool import rotate_newnym

        rotate_newnym()


def assign_proxy_slots(account_names: list[str]) -> dict[str, tuple[str, str]]:
    """Hesap listesine tor slot dağıt (2 hesap / slot)."""
    out: dict[str, tuple[str, str]] = {}
    assignments: dict[str, str] = {}
    for name in account_names:
        slot = suggest_proxy(assignments)
        assignments[name] = slot.id
        out[name] = (slot.id, slot.url)
    return out


def load_intel_summary() -> str:
    intel_path = Path(os.environ.get("DIPLOMACIA_INTEL", BOT_DIR.parent / "engagement" / "intel" / "merged.json"))
    if not intel_path.exists():
        return "Intel dosyası yok. `python3 scripts/sync_engagement.py` çalıştır."
    import json

    data = json.loads(intel_path.read_text(encoding="utf-8"))
    mc = data.get("multi_account", {})
    return (
        f"*Engagement intel* (sync: {data.get('synced_at', '?')[:19]})\n"
        f"Hedef: {data.get('target')}\n"
        f"Bulgu: {data.get('findings_count')} | Öğrenme: {data.get('learnings_count')}\n"
        f"Multi-account: {mc.get('cluster_threshold')}+ cluster, auto_ban={mc.get('auto_ban')}\n"
        f"Sinyaller: {', '.join(mc.get('signals', []))}"
    )
