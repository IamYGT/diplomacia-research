"""Fleet LLM decision contract — domain: sanitize text plans into safe targets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .fleet_missions import FleetMissionTarget

SAFE_ACCOUNT_KEYS = {
    "name",
    "role",
    "province",
    "country_id",
    "factory_id",
    "work_mode",
    "health",
    "diamonds",
    "mission",
    "runtime_state",
}
ALLOWED_ACTIONS = {
    "assign_config",
    "travel_to_province",
    "residence_set",
    "citizenship_apply",
    "independent_citizenship",
    "visa_apply",
    "election_vote",
    "province_election_vote",
    "farm_tick",
    "train_hourly",
}
ROLE_MAP = {
    "farmer": "farm",
    "farm": "farm",
    "worker": "farm",
    "warrior": "war",
    "war": "war",
    "hybrid": "hybrid",
    "karma": "hybrid",
    "hub": "hub",
    "off": "off",
}


@dataclass(frozen=True)
class FleetLlmDecision:
    target: FleetMissionTarget
    actions: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def safe_account_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop credentials/secrets before sending account state to an LLM."""
    safe: list[dict[str, Any]] = []
    for row in rows:
        item = {k: row.get(k) for k in SAFE_ACCOUNT_KEYS if k in row}
        if item:
            safe.append(item)
    return safe


def build_decision_prompt(operator_text: str, account_summaries: list[dict[str, Any]]) -> str:
    payload = {
        "operator_text_tr": operator_text[:1200],
        "accounts": safe_account_summaries(account_summaries)[:25],
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "required_json": {
            "province": "Hürmüz",
            "role": "hybrid",
            "vote": False,
            "province_vote": False,
            "independent_citizenship": False,
            "citizenship_country_id": "",
            "visa_country_id": "",
            "candidate_id": "",
            "farm_cycles": 1,
            "train_hourly": True,
            "actions": ["assign_config", "travel_to_province", "residence_set", "farm_tick", "train_hourly"],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def normalize_llm_decision(raw: dict[str, Any], fallback: Any | None = None) -> FleetLlmDecision:
    data = raw.get("target") if isinstance(raw.get("target"), dict) else raw
    warnings: list[str] = []
    province = _text(data.get("province"), _fallback(fallback, "province", "Hürmüz"))
    role = _role(data.get("role"), _fallback(fallback, "role", "hybrid"), warnings)
    target = FleetMissionTarget(
        role=role,
        factory_id=_text(data.get("factory_id"), ""),
        province=province,
        residence=_bool(data.get("residence"), True),
        citizenship_country_id=_text(data.get("citizenship_country_id"), ""),
        independent_citizenship=_bool(data.get("independent_citizenship"), False),
        visa_country_id=_text(data.get("visa_country_id"), ""),
        vote=_bool(data.get("vote"), False),
        province_vote=_bool(data.get("province_vote"), False),
        candidate_id=_text(data.get("candidate_id"), ""),
        farm_cycles=_int_range(data.get("farm_cycles"), 1, 1, 24),
    )
    actions = _actions(data, target, warnings)
    return FleetLlmDecision(target=target, actions=tuple(actions), warnings=tuple(warnings))


def _fallback(obj: Any | None, name: str, default: str) -> str:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return str(obj.get(name) or default)
    return str(getattr(obj, name, default) or default)


def _text(value: Any, default: str) -> str:
    text = str(value or default).strip()
    return text[:120]


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on", "evet", "açık")


def _int_range(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(high, parsed))


def _role(value: Any, default: str, warnings: list[str]) -> str:
    role = ROLE_MAP.get(str(value or default).strip().lower())
    if role:
        return role
    warnings.append(f"unknown_role:{value}")
    return ROLE_MAP.get(str(default).strip().lower(), "hybrid")


def _actions(data: dict[str, Any], target: FleetMissionTarget, warnings: list[str]) -> list[str]:
    requested = data.get("actions")
    if isinstance(requested, list):
        actions = []
        for item in requested:
            action = str(item or "").strip()
            if action in ALLOWED_ACTIONS:
                actions.append(action)
            elif action:
                warnings.append(f"ignored_action:{action}")
        if actions:
            return actions
    actions = ["assign_config", "travel_to_province"]
    if target.residence:
        actions.append("residence_set")
    if target.citizenship_country_id:
        actions.append("citizenship_apply")
    if target.independent_citizenship:
        actions.append("independent_citizenship")
    if target.visa_country_id:
        actions.append("visa_apply")
    if target.vote:
        actions.append("election_vote")
    if target.province_vote:
        actions.append("province_election_vote")
    actions.extend(["farm_tick", "train_hourly"])
    return actions
