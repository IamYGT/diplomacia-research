"""Fleet capability summary derived from registered API routes."""

from __future__ import annotations

from dataclasses import dataclass

from .api_route_registry import ROUTES_BY_ID


@dataclass(frozen=True)
class FleetCapability:
    key: str
    label: str
    ready: bool
    detail: str


def _has_all(*route_ids: str) -> bool:
    return all(route_id in ROUTES_BY_ID for route_id in route_ids)


def advanced_fleet_capabilities() -> tuple[FleetCapability, ...]:
    """Expose what the fleet can automate without pretending unknown APIs exist."""
    return (
        FleetCapability(
            "travel_residence",
            "seyahat+ikamet",
            _has_all("provinces.travel_start", "players.residence_set"),
            "route hazır",
        ),
        FleetCapability(
            "politics",
            "oy/vize/vatandaşlık",
            _has_all("elections.vote", "visas.apply", "citizenship.apply"),
            "route hazır",
        ),
        FleetCapability(
            "work_permit",
            "çalışma izni",
            _has_all("employment.apply"),
            "endpoint keşfi bekliyor",
        ),
        FleetCapability(
            "training_create",
            "antrenman savaşı oluşturma",
            _has_all("training.create"),
            "endpoint keşfi bekliyor; mevcut savaşa saldırı hazır",
        ),
    )


def format_fleet_capability_line() -> str:
    caps = advanced_fleet_capabilities()
    ready = [c.label for c in caps if c.ready]
    waiting = [f"{c.label}: {c.detail}" for c in caps if not c.ready]
    parts: list[str] = []
    if ready:
        parts.append("hazır " + ", ".join(ready))
    if waiting:
        parts.append("bekliyor " + " · ".join(waiting))
    return "🧭 Gelişmiş kabiliyet: " + " | ".join(parts)
