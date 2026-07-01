"""Filo günlük metrikler — action_log + training state."""

from __future__ import annotations

import time

from .auth import scoped_list_accounts
from .health_state import load_health_state


def _account_names(telegram_user_id: int) -> list[str]:
    return [a.name.strip().lower() for a in scoped_list_accounts(telegram_user_id)]


def count_fleet_farms_24h(telegram_user_id: int) -> int:
    from .action_log_query import count_actions_since

    names = _account_names(telegram_user_id)
    if not names:
        return 0
    since = time.time() - 86400
    return count_actions_since(
        account_names=names,
        action="autofarm",
        since_unix=since,
        success_only=True,
    )


def count_fleet_training_attacks_24h(telegram_user_id: int) -> int:
    """action_log training_attack + health_state fallback."""
    names = _account_names(telegram_user_id)
    if not names:
        return 0
    since = time.time() - 86400
    from .action_log_query import count_actions_since

    logged = count_actions_since(
        account_names=names,
        action="training_attack",
        since_unix=since,
    )
    bucket = dict(load_health_state().get("training_watch_last_attack") or {})
    names_set = set(names)
    state_count = sum(
        1 for name, ts in bucket.items() if name in names_set and float(ts or 0) >= since
    )
    return max(logged, state_count)


def format_fleet_metrics_line(telegram_user_id: int) -> str:
    farms = count_fleet_farms_24h(telegram_user_id)
    attacks = count_fleet_training_attacks_24h(telegram_user_id)
    if farms == 0 and attacks == 0:
        return ""
    return f"📊 Son 24s: 🌾 {farms} farm · ⚔️ {attacks} antrenman"
