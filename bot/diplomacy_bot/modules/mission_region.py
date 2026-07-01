"""Mission region phases — citizenship, visa and election actions."""

from __future__ import annotations

from ..account_config import AccountConfig
from .economy import default_api
from .mission_types import MissionRuntime, MissionStepResult, PhaseSpec, PhaseStatus

ApiFn = type(default_api)


def _done(rt: MissionRuntime, spec: PhaseSpec, action: dict, *, ok: bool = True) -> MissionStepResult:
    return MissionStepResult(
        rt.account_name,
        rt.mission_id,
        spec.phase,
        PhaseStatus.DONE,
        ok=ok,
        actions=[action],
    )


def phase_citizenship_apply(
    token: str,
    cfg: AccountConfig,
    rt: MissionRuntime,
    spec: PhaseSpec,
    *,
    _api: ApiFn,
) -> MissionStepResult:
    from ..fleet_residence import apply_citizenship, get_citizenship_info

    country_id = str((spec.params or {}).get("country_id") or "").strip()
    if not country_id:
        return _done(rt, spec, {"citizenship": {"skipped": "country_id_missing"}})
    info = get_citizenship_info(token, _api=_api)
    status = str(info.get("status") or "").lower()
    if status in ("citizen", "approved", "active"):
        return _done(rt, spec, {"citizenship": {"skipped": "already_citizen", "status": status}})
    result = apply_citizenship(token, country_id, _api=_api)
    return _done(rt, spec, {"citizenship": result}, ok=bool(result.get("ok")))


def phase_visa_apply(
    token: str,
    cfg: AccountConfig,
    rt: MissionRuntime,
    spec: PhaseSpec,
    *,
    _api: ApiFn,
) -> MissionStepResult:
    from ..fleet_residence import apply_visa

    country_id = str((spec.params or {}).get("country_id") or "").strip()
    if not country_id:
        return _done(rt, spec, {"visa": {"skipped": "country_id_missing"}})
    result = apply_visa(token, country_id, _api=_api)
    return _done(rt, spec, {"visa": result}, ok=bool(result.get("ok")))


def phase_election_vote(
    token: str,
    cfg: AccountConfig,
    rt: MissionRuntime,
    spec: PhaseSpec,
    *,
    _api: ApiFn,
) -> MissionStepResult:
    from ..fleet_residence import cast_election_vote

    candidate_id = str((spec.params or {}).get("candidate_id") or "").strip() or None
    result = cast_election_vote(token, candidate_id=candidate_id, _api=_api)
    if not result.get("ok") and str(result.get("error") or "").lower() in (
        "oy verilecek aday yok",
        "seçim yok",
    ):
        return _done(rt, spec, {"vote": {**result, "skipped": "no_active_candidate"}})
    return _done(rt, spec, {"vote": result}, ok=bool(result.get("ok")))
