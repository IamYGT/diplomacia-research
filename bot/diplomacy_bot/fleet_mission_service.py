"""Fleet mission service — scoped hesaplara kalıcı AOD planı yazar."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .domain.fleet_missions import FleetMissionTarget, build_aod_phase_dicts, build_region_phase_dicts
from .fleet_command import FleetBatchResult, FleetOpResult, resolve_operator_factory


@dataclass
class FleetMissionEnqueueResult:
    fleet_id: str
    batch: FleetBatchResult = field(default_factory=FleetBatchResult)
    phases: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FleetAutopilotResult:
    telegram_user_id: int
    province: str
    inbox: FleetBatchResult
    repair: FleetBatchResult
    mission: FleetMissionEnqueueResult


def start_fleet_autopilot_for_uid(
    telegram_user_id: int,
    *,
    province: str = "Hürmüz",
    role: str = "hybrid",
    citizenship_country_id: str = "",
    independent_citizenship: bool = False,
    visa_country_id: str = "",
    vote: bool = False,
    province_vote: bool = False,
    candidate_id: str = "",
) -> FleetAutopilotResult:
    """Tek operatör aksiyonu: inbox import, otonomi onarım, kalıcı bölge mission."""
    from .fleet_inbox_import import import_inbox_for_uid
    from .fleet_autonomy_repair import repair_fleet_autonomy_for_uid

    inbox = import_inbox_for_uid(telegram_user_id)
    repair = repair_fleet_autonomy_for_uid(telegram_user_id, role=role)
    mission = enqueue_region_missions_for_uid(
        telegram_user_id,
        province=province,
        role=role,
        citizenship_country_id=citizenship_country_id,
        independent_citizenship=independent_citizenship,
        visa_country_id=visa_country_id,
        vote=vote,
        province_vote=province_vote,
        candidate_id=candidate_id,
    )
    return FleetAutopilotResult(
        telegram_user_id=telegram_user_id,
        province=province,
        inbox=inbox,
        repair=repair,
        mission=mission,
    )


def enqueue_aod_missions_for_uid(
    telegram_user_id: int,
    *,
    province: str = "Hürmüz",
    role: str = "hybrid",
) -> FleetMissionEnqueueResult:
    """Kullanıcının alt hesapları için kalıcı AOD mission kuyruğu oluştur."""
    from .account_main import get_main_account_name
    from .auth import scoped_list_accounts
    from .mission_store import enqueue_phase_plan

    fleet_id = f"fleet-{uuid.uuid4().hex[:8]}"
    result = FleetMissionEnqueueResult(fleet_id=fleet_id)
    fid, auto_prov, err = resolve_operator_factory(telegram_user_id)
    if err or not fid:
        result.batch.add(FleetOpResult("-", False, err or "fabrika bulunamadı"))
        return result

    target = FleetMissionTarget(
        role=role,
        factory_id=fid,
        province=province or auto_prov or "Hürmüz",
        fleet_id=fleet_id,
    )
    main = (get_main_account_name(telegram_user_id) or "").strip().lower()
    for acc in scoped_list_accounts(telegram_user_id):
        if main and acc.name == main:
            continue
        try:
            phases = build_aod_phase_dicts(target)
            result.phases = [str(p.get("phase") or "") for p in phases]
            enqueue_phase_plan(
                acc.name,
                phases,
                source="fleet_aod",
                mission_id=f"{fleet_id}:{acc.name}",
                war_label=f"AOD {target.province}",
            )
            result.batch.add(FleetOpResult(acc.name, True, f"AOD mission → {target.province}"))
        except Exception as e:
            result.batch.add(FleetOpResult(acc.name, False, str(e)[:80]))
    return result


def enqueue_region_missions_for_uid(
    telegram_user_id: int,
    *,
    province: str = "Hürmüz",
    role: str = "hybrid",
    citizenship_country_id: str = "",
    independent_citizenship: bool = False,
    visa_country_id: str = "",
    vote: bool = False,
    province_vote: bool = False,
    candidate_id: str = "",
) -> FleetMissionEnqueueResult:
    """Bölge taşıma mission'ı: worker seyahat/ikamet/izin/oy/farm fazlarını sürdürür."""
    from .account_main import get_main_account_name
    from .auth import scoped_list_accounts
    from .mission_store import enqueue_phase_plan

    fleet_id = f"region-{uuid.uuid4().hex[:8]}"
    result = FleetMissionEnqueueResult(fleet_id=fleet_id)
    fid, auto_prov, err = resolve_operator_factory(telegram_user_id)
    if err or not fid:
        result.warnings.append(err or "Ana fabrika UUID yok — /fleetfactory main")
    target = FleetMissionTarget(
        role=role,
        factory_id=fid or "",
        province=province or auto_prov or "Hürmüz",
        fleet_id=fleet_id,
        citizenship_country_id=citizenship_country_id,
        independent_citizenship=independent_citizenship,
        visa_country_id=visa_country_id,
        vote=vote,
        province_vote=province_vote,
        candidate_id=candidate_id,
        farm_cycles=1,
    )
    phases = build_region_phase_dicts(target)
    result.phases = [str(p.get("phase") or "") for p in phases]
    main = (get_main_account_name(telegram_user_id) or "").strip().lower()
    for acc in scoped_list_accounts(telegram_user_id):
        if main and acc.name == main:
            continue
        try:
            enqueue_phase_plan(
                acc.name,
                phases,
                source="fleet_region",
                mission_id=f"{fleet_id}:{acc.name}",
                war_label=f"Region {target.province}",
            )
            result.batch.add(FleetOpResult(acc.name, True, f"region mission → {target.province}"))
        except Exception as e:
            result.batch.add(FleetOpResult(acc.name, False, str(e)[:80]))
    return result
