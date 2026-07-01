"""Mission stat helpers — keep mission executor small."""

from __future__ import annotations

from ..account_config import AccountConfig
from . import stats
from .economy import ApiFn, default_api


def stat_actions(
    token: str,
    cfg: AccountConfig,
    *,
    suffix: str = "",
    _api: ApiFn = default_api,
) -> list[dict]:
    """Run stat automation and return mission action entries."""
    if not getattr(cfg, "stat_auto_enabled", False):
        return []
    result = stats.run_stat_automation(token, cfg, _api=_api)
    actions: list[dict] = []
    if result.get("passive"):
        actions.append({f"passive_stats{suffix}": result["passive"]})
    if result.get("upgrades"):
        actions.append({f"stat_upgrades{suffix}": result["upgrades"]})
    return actions
