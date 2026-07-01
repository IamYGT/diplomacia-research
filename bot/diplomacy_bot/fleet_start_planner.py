"""Fleet start planner — service: resolve command text into autopilot kwargs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from .fleet_region_mission_ui import parse_region_args

log = logging.getLogger(__name__)

PlannerFn = Callable[[str, list[dict[str, Any]], Any], Any]

_NATURAL_HINTS = (
    "hesap",
    "hesapları",
    "gönder",
    "götür",
    "çek",
    "çalış",
    "fabrika",
    "farm",
    "antrenman",
    "otomatik",
    "bölge",
    "ikamet",
)


@dataclass(frozen=True)
class FleetStartPlan:
    province: str
    opts: dict[str, Any]
    source: str = "parser"
    warnings: tuple[str, ...] = ()


def resolve_fleet_start_plan(
    telegram_user_id: int,
    args: list[str],
    *,
    _planner: PlannerFn | None = None,
) -> FleetStartPlan:
    province, opts = parse_region_args(args)
    fallback = {"province": province, **opts}
    text = " ".join(args).strip()
    if not text or not (_planner or _should_use_deepseek(args)):
        return FleetStartPlan(_clean_province(text, province), opts)
    try:
        planner = _planner or _deepseek_planner
        decision = planner(text, _account_summaries(telegram_user_id), fallback)
        return FleetStartPlan(
            decision.target.province,
            _target_opts(decision.target),
            source="deepseek",
            warnings=decision.warnings,
        )
    except Exception as e:
        log.warning("fleet_start_deepseek_fallback: %s", e)
        return FleetStartPlan(
            _clean_province(text, province),
            opts,
            warnings=(f"deepseek_fallback:{type(e).__name__}",),
        )


def _should_use_deepseek(args: list[str]) -> bool:
    from . import config

    if not config.DEEPSEEK_API_KEY:
        return False
    text = " ".join(args).strip().lower()
    return len(args) >= 5 or any(hint in text for hint in _NATURAL_HINTS)


def _deepseek_planner(text: str, summaries: list[dict[str, Any]], fallback: Any) -> Any:
    from .adapters.deepseek_fleet_planner import plan_fleet_with_deepseek

    return plan_fleet_with_deepseek(text, summaries, fallback=fallback)


def _account_summaries(telegram_user_id: int) -> list[dict[str, Any]]:
    from .auth import scoped_list_accounts

    rows: list[dict[str, Any]] = []
    for acc in scoped_list_accounts(telegram_user_id):
        rows.append(
            {
                "name": acc.name,
                "status": acc.status,
                "runtime_state": acc.runtime_state,
                "diamonds": acc.last_balance,
            }
        )
    return rows


def _target_opts(target: Any) -> dict[str, Any]:
    return {
        "citizenship_country_id": target.citizenship_country_id,
        "independent_citizenship": target.independent_citizenship,
        "visa_country_id": target.visa_country_id,
        "vote": target.vote,
        "province_vote": target.province_vote,
        "candidate_id": target.candidate_id,
    }


def _clean_province(text: str, parsed: str) -> str:
    low = text.lower()
    if "hürmüz" in low or "hurmuz" in low or "aod" in low:
        return "Hürmüz"
    if "tahran" in low:
        return "Tahran"
    return parsed
