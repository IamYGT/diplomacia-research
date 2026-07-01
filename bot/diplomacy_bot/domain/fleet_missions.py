"""Fleet mission planning — domain: hedefi phase sözlüğüne çevirir."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FleetMissionTarget:
    role: str = "hybrid"
    factory_id: str = ""
    province: str = "Hürmüz"
    residence: bool = True
    citizenship_country_id: str = ""
    visa_country_id: str = ""
    vote: bool = False
    candidate_id: str = ""
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
    if target.citizenship_country_id:
        phases.append(
            {"phase": "citizenship_apply", "params": {"country_id": target.citizenship_country_id}}
        )
    if target.visa_country_id:
        phases.append({"phase": "visa_apply", "params": {"country_id": target.visa_country_id}})
    if target.vote:
        phases.append({"phase": "election_vote", "params": {"candidate_id": target.candidate_id}})
    phases.append({"phase": "farm_tick", "farm_cycles": max(1, int(target.farm_cycles))})
    return phases


def build_region_phase_dicts(target: FleetMissionTarget) -> list[dict]:
    """Genel bölge operasyonu: config opsiyonel, seyahat/ikamet + izin/oy."""
    phases: list[dict] = []
    if target.role or target.factory_id:
        params = {
            "role": target.role,
            "factory_id": target.factory_id,
            "province": target.province,
            "fleet_id": target.fleet_id,
        }
        phases.append({"phase": "assign_config", "params": params})
    if target.province:
        phases.append({"phase": "travel_to_province", "params": {"province": target.province}})
    if target.residence:
        phases.append({"phase": "residence_set", "params": {"province": target.province}})
    if target.citizenship_country_id:
        phases.append(
            {"phase": "citizenship_apply", "params": {"country_id": target.citizenship_country_id}}
        )
    if target.visa_country_id:
        phases.append({"phase": "visa_apply", "params": {"country_id": target.visa_country_id}})
    if target.vote:
        phases.append({"phase": "election_vote", "params": {"candidate_id": target.candidate_id}})
    if target.farm_cycles:
        phases.append({"phase": "farm_tick", "farm_cycles": max(1, int(target.farm_cycles))})
    return phases
