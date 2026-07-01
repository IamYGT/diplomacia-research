from __future__ import annotations

import json
import time
import uuid
from .modules.mission_types import (
    MissionPhase,
    MissionPlan,
    MissionRuntime,
    PhaseSpec,
    PhaseStatus,
)


def _conn():
    from .store import _conn as store_conn

    return store_conn()


def _phase_to_dict(p: PhaseSpec) -> dict:
    return {
        "phase": p.phase.value,
        "target_war_id": p.target_war_id,
        "contribute_side": p.contribute_side,
        "farm_cycles": p.farm_cycles,
        "max_contributions": p.max_contributions,
        "params": p.params,
    }


def _phase_from_dict(d: dict) -> PhaseSpec:
    return PhaseSpec(
        phase=MissionPhase(d["phase"]),
        target_war_id=d.get("target_war_id"),
        contribute_side=d.get("contribute_side") or "auto",
        farm_cycles=int(d.get("farm_cycles") or 1),
        max_contributions=int(d.get("max_contributions") or 1),
        params=dict(d.get("params") or {}),
    )


def _plan_to_json(plan: MissionPlan) -> str:
    return json.dumps(
        {
            "mission_id": plan.mission_id,
            "account_name": plan.account_name,
            "phases": [_phase_to_dict(p) for p in plan.phases],
            "source": plan.source,
            "war_label": plan.war_label,
            "created_at": plan.created_at,
        },
        ensure_ascii=False,
    )


def _plan_from_json(raw: str) -> MissionPlan:
    d = json.loads(raw)
    return MissionPlan(
        mission_id=d["mission_id"],
        account_name=d["account_name"],
        phases=[_phase_from_dict(p) for p in d.get("phases") or []],
        source=d.get("source") or "user",
        war_label=d.get("war_label"),
        created_at=float(d.get("created_at") or 0),
    )


def _runtime_to_json(rt: MissionRuntime) -> str:
    return json.dumps(
        {
            "mission_id": rt.mission_id,
            "account_name": rt.account_name,
            "phase_index": rt.phase_index,
            "phase_status": rt.phase_status.value,
            "wait_until": rt.wait_until,
            "wait_reason": rt.wait_reason,
            "contributions_done": rt.contributions_done,
            "farm_cycles_done": rt.farm_cycles_done,
            "last_error": rt.last_error,
            "updated_at": rt.updated_at,
        },
        ensure_ascii=False,
    )


def _runtime_from_json(plan: MissionPlan, raw: str) -> MissionRuntime:
    d = json.loads(raw)
    return MissionRuntime(
        mission_id=d["mission_id"],
        account_name=d["account_name"],
        plan=plan,
        phase_index=int(d.get("phase_index") or 0),
        phase_status=PhaseStatus(d.get("phase_status") or PhaseStatus.PENDING.value),
        wait_until=d.get("wait_until"),
        wait_reason=d.get("wait_reason"),
        contributions_done=int(d.get("contributions_done") or 0),
        farm_cycles_done=int(d.get("farm_cycles_done") or 0),
        last_error=d.get("last_error"),
        updated_at=float(d.get("updated_at") or 0),
    )


def get_active_mission(account_name: str) -> MissionRuntime | None:
    name = account_name.strip().lower()
    with _conn() as c:
        row = c.execute(
            "SELECT plan_json, runtime_json, status FROM account_missions WHERE account_name=? AND status IN ('active','waiting')",
            (name,),
        ).fetchone()
    if not row:
        return None
    plan = _plan_from_json(row["plan_json"])
    return _runtime_from_json(plan, row["runtime_json"])


def save_mission_runtime(rt: MissionRuntime, *, status: str = "active") -> None:
    now = time.time()
    rt.updated_at = now
    with _conn() as c:
        c.execute(
            """
            INSERT INTO account_missions (account_name, mission_id, status, plan_json, runtime_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                mission_id=excluded.mission_id,
                status=excluded.status,
                plan_json=excluded.plan_json,
                runtime_json=excluded.runtime_json,
                updated_at=excluded.updated_at
            """,
            (
                rt.account_name,
                rt.mission_id,
                status,
                _plan_to_json(rt.plan),
                _runtime_to_json(rt),
                rt.plan.created_at or now,
                now,
            ),
        )


def clear_mission(account_name: str, *, status: str = "cancelled") -> None:
    name = account_name.strip().lower()
    with _conn() as c:
        c.execute(
            "UPDATE account_missions SET status=?, updated_at=? WHERE account_name=?",
            (status, time.time(), name),
        )


def _default_phases(
    account_name: str,
    *,
    target_war_id: str | None,
    contribute_side: str,
    farm_cycles: int,
) -> list[PhaseSpec]:
    from .account_config import get_config

    cfg = get_config(account_name)
    phases: list[PhaseSpec] = []
    if cfg.war_enabled:
        phases.append(
            PhaseSpec(
                MissionPhase.WAR_TICK,
                target_war_id=target_war_id,
                contribute_side=contribute_side,
                max_contributions=1,
            )
        )
    phases.append(PhaseSpec(MissionPhase.FARM_TICK, farm_cycles=farm_cycles))
    if cfg.training_enabled:
        phases.append(PhaseSpec(MissionPhase.TRAIN_TICK))
    return phases


def enqueue_mission(
    account_name: str,
    *,
    target_war_id: str | None = None,
    contribute_side: str = "auto",
    war_label: str | None = None,
    farm_cycles: int = 3,
) -> MissionRuntime:
    now = time.time()
    mid = f"m-{uuid.uuid4().hex[:10]}"
    name = account_name.strip().lower()
    plan = MissionPlan(
        mission_id=mid,
        account_name=name,
        war_label=war_label,
        created_at=now,
        phases=_default_phases(
            name,
            target_war_id=target_war_id,
            contribute_side=contribute_side,
            farm_cycles=farm_cycles,
        ),
    )
    rt = MissionRuntime(
        mission_id=mid,
        account_name=plan.account_name,
        plan=plan,
        updated_at=now,
    )
    save_mission_runtime(rt, status="active")
    from .store import set_runtime_state

    set_runtime_state(plan.account_name, "mission_active")
    return rt


def enqueue_phase_plan(
    account_name: str,
    phase_dicts: list[dict],
    *,
    source: str = "fleet",
    mission_id: str | None = None,
    war_label: str | None = None,
) -> MissionRuntime:
    now = time.time()
    mid = mission_id or f"m-{uuid.uuid4().hex[:10]}"
    name = account_name.strip().lower()
    plan = MissionPlan(
        mission_id=mid,
        account_name=name,
        phases=[_phase_from_dict(p) for p in phase_dicts],
        source=source,
        war_label=war_label,
        created_at=now,
    )
    rt = MissionRuntime(mid, name, plan, updated_at=now)
    save_mission_runtime(rt, status="active")
    from .store import set_runtime_state

    set_runtime_state(name, "mission_active")
    return rt
