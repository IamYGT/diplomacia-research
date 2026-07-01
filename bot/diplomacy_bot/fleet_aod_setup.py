"""AOD zincir kurulumu — bootstrap → fabrika → seyahat → ikamet."""

from __future__ import annotations

from .fleet_command import (
    FleetBatchResult,
    FleetOpResult,
    assign_fleet_to_factory,
    bootstrap_fleet,
    resolve_operator_factory,
    travel_fleet,
)
from .fleet_residence import DEFAULT_RESIDENCE_PROVINCE, set_fleet_residence


def run_aod_setup(
    telegram_user_id: int,
    *,
    province: str = DEFAULT_RESIDENCE_PROVINCE,
) -> dict[str, FleetBatchResult]:
    """Tek zincir: bootstrap → fabrika → seyahat → ikamet."""
    prov = province.strip() or DEFAULT_RESIDENCE_PROVINCE
    steps: dict[str, FleetBatchResult] = {
        "bootstrap": bootstrap_fleet(telegram_user_id, role="hybrid"),
    }
    fid, _, factory_err = resolve_operator_factory(telegram_user_id)
    if factory_err or not fid:
        skip = FleetBatchResult()
        skip.add(
            FleetOpResult(
                "-",
                False,
                f"⏭ atlandı — {factory_err or 'fabrika UUID yok'}",
            )
        )
        steps["factory"] = skip
    else:
        steps["factory"] = assign_fleet_to_factory(telegram_user_id, province=prov)
    steps["travel"] = travel_fleet(telegram_user_id, prov)
    steps["residence"] = set_fleet_residence(telegram_user_id, prov)
    return steps
