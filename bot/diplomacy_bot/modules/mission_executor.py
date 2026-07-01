from __future__ import annotations

import time

from ..account_config import AccountConfig, get_config, update_config_field
from ..mission_store import clear_mission, save_mission_runtime
from ..war_ops import run_war_contribute
from . import economy, factory, training, travel
from .economy import default_api
from .mission_region import (
    phase_citizenship_apply,
    phase_election_vote,
    phase_independent_citizenship,
    phase_visa_apply,
)
from .mission_types import MissionPhase, MissionRuntime, MissionStepResult, PhaseSpec, PhaseStatus
from .orchestrator import TickResult, tick_account


def _mission_step_to_tick(step: MissionStepResult) -> TickResult:
    tr = TickResult(account_name=step.account_name)
    tr.ok = step.ok or step.blocked or step.mission_complete
    tr.actions = list(step.actions)
    tr.error = step.error
    if step.mission_complete:
        tr.actions.append({"mission": "complete"})
    elif step.blocked and step.wait_ms:
        tr.actions.append({"cooldown_ms": step.wait_ms, "mission_wait": step.phase_status.value})
    return tr

ApiFn = type(default_api)


def _advance_waiting(rt: MissionRuntime, reason: str, wait_ms: int) -> MissionStepResult:
    rt.phase_status = PhaseStatus.WAITING
    rt.wait_reason = reason
    rt.wait_until = time.time() + wait_ms / 1000.0
    spec = rt.plan.phases[rt.phase_index]
    save_mission_runtime(rt, status="waiting")
    return MissionStepResult(
        account_name=rt.account_name,
        mission_id=rt.mission_id,
        phase=spec.phase,
        phase_status=PhaseStatus.WAITING,
        blocked=True,
        wait_ms=wait_ms,
    )


def _phase_war(token: str, cfg: AccountConfig, rt: MissionRuntime, spec: PhaseSpec, *, _api: ApiFn) -> MissionStepResult:
    if spec.target_war_id:
        update_config_field(rt.account_name, target_war_id=spec.target_war_id, war_enabled=True)
        if spec.contribute_side in ("attacker", "defender"):
            update_config_field(rt.account_name, contribute_side=spec.contribute_side)
    side = spec.contribute_side if spec.contribute_side in ("attacker", "defender") else None
    pack = run_war_contribute(token, rt.account_name, war_id=spec.target_war_id, side=side, _api=_api)
    if pack.get("skipped") == "war_cooldown":
        return _advance_waiting(rt, "war_cooldown", int(pack.get("cooldown_ms") or 600_000))
    if pack.get("skipped") == "traveling":
        return _advance_waiting(rt, "travel", int(pack.get("remaining_ms") or 60_000))
    rt.contributions_done += 1
    if pack.get("ok"):
        if rt.contributions_done >= spec.max_contributions:
            return MissionStepResult(
                rt.account_name, rt.mission_id, spec.phase, PhaseStatus.DONE, ok=True, actions=[pack]
            )
        return MissionStepResult(
            rt.account_name, rt.mission_id, spec.phase, PhaseStatus.IN_PROGRESS, ok=True, actions=[pack]
        )
    if pack.get("skipped"):
        return MissionStepResult(
            rt.account_name,
            rt.mission_id,
            spec.phase,
            PhaseStatus.SKIPPED,
            ok=False,
            actions=[pack],
            error=str(pack.get("skipped")),
        )
    return MissionStepResult(
        rt.account_name, rt.mission_id, spec.phase, PhaseStatus.FAILED, error=pack.get("error")
    )


def _phase_assign_config(
    token: str,
    cfg: AccountConfig,
    rt: MissionRuntime,
    spec: PhaseSpec,
    *,
    _api: ApiFn,
) -> MissionStepResult:
    params = dict(spec.params or {})
    role = str(params.get("role") or "hybrid")
    factory_id = str(params.get("factory_id") or "").strip()
    fields = {
        "role": role,
        "stat_auto_enabled": True,
        "training_enabled": True,
        "craft_pills_when_low": True,
        "auto_travel_enabled": True,
    }
    if factory_id:
        fields.update({"work_mode": "fixed", "preferred_factory_id": factory_id})
    update_config_field(rt.account_name, **fields)
    from ..store import set_autofarm

    set_autofarm(rt.account_name, True)
    return MissionStepResult(
        rt.account_name,
        rt.mission_id,
        spec.phase,
        PhaseStatus.DONE,
        ok=True,
        actions=[{"assign_config": {"role": role, "factory_id": factory_id}}],
    )


def _phase_travel_to_province(
    token: str,
    cfg: AccountConfig,
    rt: MissionRuntime,
    spec: PhaseSpec,
    *,
    _api: ApiFn,
) -> MissionStepResult:
    province = str((spec.params or {}).get("province") or "").strip()
    if not province:
        return MissionStepResult(rt.account_name, rt.mission_id, spec.phase, PhaseStatus.FAILED, error="province missing")
    tr = travel.ensure_in_province(token, province, leave_factory_first=True, _api=_api)
    if tr.get("ok") and not tr.get("traveling"):
        return MissionStepResult(
            rt.account_name, rt.mission_id, spec.phase, PhaseStatus.DONE, ok=True, actions=[{"travel": tr}]
        )
    if tr.get("ok") and tr.get("traveling"):
        return _advance_waiting(rt, "travel", int(tr.get("remaining_ms") or 60_000))
    return MissionStepResult(
        rt.account_name, rt.mission_id, spec.phase, PhaseStatus.FAILED, error=str(tr.get("error") or "travel failed")
    )


def _phase_residence_set(
    token: str,
    cfg: AccountConfig,
    rt: MissionRuntime,
    spec: PhaseSpec,
    *,
    _api: ApiFn,
) -> MissionStepResult:
    province = str((spec.params or {}).get("province") or "").strip()
    if not province:
        return MissionStepResult(rt.account_name, rt.mission_id, spec.phase, PhaseStatus.FAILED, error="province missing")
    if travel.is_traveling(token, _api=_api):
        ts = travel.get_travel_status(token, _api=_api)
        return _advance_waiting(rt, "travel", int(ts.remaining_ms if ts else 60_000))
    from ..fleet_residence import set_residence

    r = set_residence(token, province, _api=_api)
    if r.get("ok"):
        return MissionStepResult(
            rt.account_name, rt.mission_id, spec.phase, PhaseStatus.DONE, ok=True, actions=[{"residence": r}]
        )
    return MissionStepResult(
        rt.account_name,
        rt.mission_id,
        spec.phase,
        PhaseStatus.FAILED,
        error=str(r.get("error") or "residence failed"),
    )


def _phase_farm(token: str, cfg: AccountConfig, rt: MissionRuntime, spec: PhaseSpec, *, _api: ApiFn) -> MissionStepResult:
    if travel.is_traveling(token, _api=_api):
        ts = travel.get_travel_status(token, _api=_api)
        return _advance_waiting(rt, "travel", int(ts.remaining_ms if ts else 60_000))
    actions: list[dict] = []
    craft = economy.ensure_pills(token, cfg, _api=_api)
    if craft:
        actions.append({"economy": craft})
    work = factory.run_work_cycle(token, cfg, _api=_api)
    actions.append({"farm": work})
    if work.get("ok"):
        rt.farm_cycles_done += 1
        if rt.farm_cycles_done >= spec.farm_cycles:
            return MissionStepResult(
                rt.account_name, rt.mission_id, spec.phase, PhaseStatus.DONE, ok=True, actions=actions
            )
        return MissionStepResult(
            rt.account_name, rt.mission_id, spec.phase, PhaseStatus.IN_PROGRESS, ok=True, actions=actions
        )
    if work.get("cooldown_ms"):
        return _advance_waiting(rt, "work_cooldown", int(work["cooldown_ms"]))
    return MissionStepResult(
        rt.account_name, rt.mission_id, spec.phase, PhaseStatus.FAILED, error=work.get("error")
    )


def _phase_train(token: str, cfg: AccountConfig, rt: MissionRuntime, spec: PhaseSpec, *, _api: ApiFn) -> MissionStepResult:
    tr = training.try_free_attack(token, cfg, _api=_api)
    if tr and tr.get("skipped") == "free_attack_cooldown":
        return _advance_waiting(rt, "training_cooldown", int(tr.get("ms") or 3_600_000))
    return MissionStepResult(
        rt.account_name, rt.mission_id, spec.phase, PhaseStatus.DONE, ok=True, actions=[{"training": tr}]
    )


def run_mission_step(
    token: str,
    rt: MissionRuntime,
    *,
    cfg: AccountConfig | None = None,
    _api: ApiFn | None = None,
) -> MissionStepResult:
    api_fn = _api or default_api
    cfg = cfg or get_config(rt.account_name)

    if rt.phase_status == PhaseStatus.WAITING and rt.wait_until and time.time() < rt.wait_until:
        return MissionStepResult(
            rt.account_name,
            rt.mission_id,
            None,
            PhaseStatus.WAITING,
            blocked=True,
            wait_ms=int((rt.wait_until - time.time()) * 1000),
        )
    if rt.phase_status == PhaseStatus.WAITING:
        rt.phase_status = PhaseStatus.IN_PROGRESS

    if rt.phase_index >= len(rt.plan.phases):
        clear_mission(rt.account_name, status="completed")
        from ..store import set_runtime_state

        set_runtime_state(rt.account_name, "idle")
        return MissionStepResult(
            rt.account_name, rt.mission_id, None, PhaseStatus.DONE, mission_complete=True, ok=True
        )

    spec = rt.plan.phases[rt.phase_index]
    handlers = {
        MissionPhase.ASSIGN_CONFIG: _phase_assign_config,
        MissionPhase.TRAVEL_TO_PROVINCE: _phase_travel_to_province,
        MissionPhase.RESIDENCE_SET: _phase_residence_set,
        MissionPhase.CITIZENSHIP_APPLY: phase_citizenship_apply,
        MissionPhase.INDEPENDENT_CITIZENSHIP: phase_independent_citizenship,
        MissionPhase.VISA_APPLY: phase_visa_apply,
        MissionPhase.ELECTION_VOTE: phase_election_vote,
        MissionPhase.WAR_TICK: _phase_war,
        MissionPhase.FARM_TICK: _phase_farm,
        MissionPhase.TRAIN_TICK: _phase_train,
    }
    result = handlers[spec.phase](token, cfg, rt, spec, _api=api_fn)

    if result.phase_status == PhaseStatus.DONE:
        rt.phase_index += 1
        rt.contributions_done = 0
        rt.farm_cycles_done = 0
        rt.phase_status = PhaseStatus.PENDING
        rt.wait_until = None
        rt.wait_reason = None
        if rt.phase_index >= len(rt.plan.phases):
            result.mission_complete = True
            clear_mission(rt.account_name, status="completed")
            from ..store import set_runtime_state

            set_runtime_state(rt.account_name, "idle")
        else:
            save_mission_runtime(rt, status="active")
    elif result.phase_status in (PhaseStatus.FAILED, PhaseStatus.SKIPPED) and result.mission_complete is False:
        rt.last_error = result.error
        save_mission_runtime(rt, status="active")
    elif result.blocked:
        save_mission_runtime(rt, status="waiting")
    else:
        save_mission_runtime(rt, status="active")

    from ..tick_activity import record_mission_step

    record_mission_step(rt.account_name, result)
    return result


def schedule_account(
    token: str,
    account_name: str,
    *,
    cfg: AccountConfig | None = None,
    _api: ApiFn | None = None,
) -> TickResult:
    from ..mission_store import get_active_mission

    rt = get_active_mission(account_name)
    if rt:
        return _mission_step_to_tick(run_mission_step(token, rt, cfg=cfg, _api=_api))
    return tick_account(token, account_name, cfg=cfg, _api=_api)
