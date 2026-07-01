"""Fleet mission service — scoped hesaplara kalıcı AOD planı yazar."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .domain.fleet_missions import FleetMissionTarget, build_aod_phase_dicts
from .fleet_command import FleetBatchResult, FleetOpResult, resolve_operator_factory


@dataclass
class FleetMissionEnqueueResult:
    fleet_id: str
    batch: FleetBatchResult = field(default_factory=FleetBatchResult)


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
