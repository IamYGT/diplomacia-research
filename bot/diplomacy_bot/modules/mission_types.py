from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MissionPhase(str, Enum):
    ASSIGN_CONFIG = "assign_config"
    TRAVEL_TO_PROVINCE = "travel_to_province"
    RESIDENCE_SET = "residence_set"
    CITIZENSHIP_APPLY = "citizenship_apply"
    INDEPENDENT_CITIZENSHIP = "independent_citizenship"
    VISA_APPLY = "visa_apply"
    ELECTION_VOTE = "election_vote"
    WAR_TICK = "war_tick"
    FARM_TICK = "farm_tick"
    TRAIN_TICK = "train_tick"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseSpec:
    phase: MissionPhase
    target_war_id: str | None = None
    contribute_side: str = "auto"
    farm_cycles: int = 1
    max_contributions: int = 1
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionPlan:
    mission_id: str
    account_name: str
    phases: list[PhaseSpec]
    source: str = "user"
    war_label: str | None = None
    created_at: float = 0.0


@dataclass
class MissionRuntime:
    mission_id: str
    account_name: str
    plan: MissionPlan
    phase_index: int = 0
    phase_status: PhaseStatus = PhaseStatus.PENDING
    wait_until: float | None = None
    wait_reason: str | None = None
    contributions_done: int = 0
    farm_cycles_done: int = 0
    last_error: str | None = None
    updated_at: float = 0.0


@dataclass
class MissionStepResult:
    account_name: str
    mission_id: str
    phase: MissionPhase | None
    phase_status: PhaseStatus
    mission_complete: bool = False
    ok: bool = False
    blocked: bool = False
    wait_ms: int | None = None
    actions: list[dict] = field(default_factory=list)
    error: str | None = None
