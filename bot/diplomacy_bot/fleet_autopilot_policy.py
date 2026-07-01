"""Fleet autopilot policy — per-operator target defaults."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

from .config import DATA_DIR

log = logging.getLogger(__name__)

_STATE_PATH = DATA_DIR / "fleet_autopilot_policy.json"


@dataclass(frozen=True)
class FleetAutopilotPolicy:
    province: str = "Hürmüz"
    role: str = "hybrid"
    citizenship_country_id: str = ""
    independent_citizenship: bool = False
    visa_country_id: str = ""
    vote: bool = False
    province_vote: bool = False
    candidate_id: str = ""

    def kwargs(self) -> dict:
        return asdict(self)


def _uid_key(telegram_user_id: int) -> str:
    return str(int(telegram_user_id))


def _load_raw() -> dict:
    if not _STATE_PATH.exists():
        return {}
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        log.warning("fleet_autopilot_policy load: %s", e)
        return {}


def _save_raw(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    tmp = _STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, _STATE_PATH)


def load_fleet_autopilot_policy(telegram_user_id: int) -> FleetAutopilotPolicy:
    raw = _load_raw().get(_uid_key(telegram_user_id)) or {}
    if not isinstance(raw, dict):
        raw = {}
    return FleetAutopilotPolicy(
        province=str(raw.get("province") or "Hürmüz"),
        role=str(raw.get("role") or "hybrid"),
        citizenship_country_id=str(raw.get("citizenship_country_id") or ""),
        independent_citizenship=bool(raw.get("independent_citizenship")),
        visa_country_id=str(raw.get("visa_country_id") or ""),
        vote=bool(raw.get("vote")),
        province_vote=bool(raw.get("province_vote")),
        candidate_id=str(raw.get("candidate_id") or ""),
    )


def save_fleet_autopilot_policy(telegram_user_id: int, policy: FleetAutopilotPolicy) -> None:
    data = _load_raw()
    data[_uid_key(telegram_user_id)] = policy.kwargs()
    _save_raw(data)


def policy_from_region_args(province: str, opts: dict, *, role: str = "hybrid") -> FleetAutopilotPolicy:
    return FleetAutopilotPolicy(
        province=province or "Hürmüz",
        role=role or "hybrid",
        citizenship_country_id=str(opts.get("citizenship_country_id") or ""),
        independent_citizenship=bool(opts.get("independent_citizenship")),
        visa_country_id=str(opts.get("visa_country_id") or ""),
        vote=bool(opts.get("vote")),
        province_vote=bool(opts.get("province_vote")),
        candidate_id=str(opts.get("candidate_id") or ""),
    )
