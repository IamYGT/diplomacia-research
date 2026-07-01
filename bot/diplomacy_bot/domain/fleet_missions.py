"""Fleet mission planning — domain: hedefi phase sözlüğüne çevirir."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FleetMissionTarget:
    role: str = "hybrid"
    factory_id: str = ""
    province: str = "Hürmüz"
    residence: bool = True
    farm_cycles: int = 1
    fleet_id: str = ""


def build_aod_phase_dicts(target: FleetMissionTarget) -> list[dict]:
    """AOD hedefi için kalıcı mission phase sözlükleri üret."""
    params = {
        "role": target.role,
        "factory_id": target.factory_id,
        "province": target.province,
        "fleet_id": target.fleet_id,
    }
    phases = [
        {"phase": "assign_config", "params": params},
        {"phase": "travel_to_province", "params": {"province": target.province}},
    ]
    if target.residence:
        phases.append({"phase": "residence_set", "params": {"province": target.province}})
    phases.append({"phase": "farm_tick", "farm_cycles": max(1, int(target.farm_cycles))})
    return phases
