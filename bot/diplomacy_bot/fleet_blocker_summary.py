"""Fleet blocker summary — concise status diagnostics."""

from __future__ import annotations

import time
from collections import Counter
from typing import Iterable

from .fleet_autonomy_audit import FleetAudit
from .store import Account

_RUNTIME_LABELS = {
    "traveling": "seyahat",
    "cooldown": "cooldown",
    "off": "kapalı",
}

_TRAINING_LABELS = {
    "no_training_war": "training savaş yok",
    "no_training_war_id": "training id yok",
    "free_attack_cooldown": "training cooldown",
    "no_result": "training sonuç yok",
}


def _names(accounts: Iterable[Account]) -> list[str]:
    return [a.name.strip().lower() for a in accounts if a.name.strip()]


def _runtime_counts(accounts: Iterable[Account]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for acc in accounts:
        label = _RUNTIME_LABELS.get((acc.runtime_state or "").strip().lower())
        if label:
            counts[label] += 1
    return counts


def _training_skip_counts(account_names: list[str]) -> Counter[str]:
    from .action_log_query import count_action_results_since

    raw = count_action_results_since(
        account_names=account_names,
        action="training_skip",
        since_unix=time.time() - 86400,
    )
    counts: Counter[str] = Counter()
    for result, count in raw.items():
        label = _TRAINING_LABELS.get(result.strip().lower())
        if label:
            counts[label] += int(count)
    return counts


def format_fleet_blocker_summary(accounts: list[Account], audit: FleetAudit) -> str:
    if audit.total <= 0:
        return ""
    parts: list[str] = []
    if audit.ready < audit.total:
        parts.append(f"{audit.total - audit.ready} hazır değil")
    counts = _runtime_counts(accounts)
    counts.update(_training_skip_counts(_names(accounts)))
    for label, count in counts.most_common(4):
        if count > 0:
            parts.append(f"{count} {label}")
    if not parts:
        return "🧯 Darboğaz: görünür engel yok"
    return "🧯 Darboğaz: " + " · ".join(parts[:5])
