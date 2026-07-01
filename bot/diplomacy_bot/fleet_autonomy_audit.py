"""Fleet autonomy audit — domain-level readiness checklist."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .account_config import get_config, normalize_role
from .store import Account


@dataclass
class FleetAuditRow:
    account_name: str
    ready: bool
    blockers: list[str] = field(default_factory=list)
    mission: str = ""


@dataclass
class FleetAudit:
    total: int
    ready: int
    rows: list[FleetAuditRow] = field(default_factory=list)

    @property
    def blockers(self) -> list[FleetAuditRow]:
        return [r for r in self.rows if not r.ready]


def _mission_label(account_name: str) -> str:
    try:
        from .mission_store import get_active_mission

        rt = get_active_mission(account_name)
        if not rt:
            return ""
        if rt.phase_index >= len(rt.plan.phases):
            phase = "done"
        else:
            phase = rt.plan.phases[rt.phase_index].phase.value
        return f"{phase}:{rt.phase_status.value}"
    except Exception:
        return ""


def audit_fleet_autonomy(
    accounts: Iterable[Account],
    *,
    factory_id: str = "",
    main_account_name: str = "",
) -> FleetAudit:
    """Check whether worker accounts can run unattended non-premium automation."""
    main = main_account_name.strip().lower()
    fid = factory_id.strip()
    rows: list[FleetAuditRow] = []
    for acc in accounts:
        name = acc.name.strip().lower()
        if main and name == main:
            continue
        cfg = get_config(name)
        role = normalize_role(cfg.role)
        blockers: list[str] = []
        if acc.status and acc.status != "active":
            blockers.append("pasif hesap")
        if not acc.autofarm:
            blockers.append("autofarm kapalı")
        if role in ("off", "hub"):
            blockers.append(f"rol {role}")
        if not cfg.stat_auto_enabled:
            blockers.append("stat auto kapalı")
        if not cfg.training_enabled:
            blockers.append("antrenman kapalı")
        if not cfg.craft_pills_when_low:
            blockers.append("hap craft kapalı")
        if not cfg.auto_travel_enabled:
            blockers.append("oto seyahat kapalı")
        if fid and ((cfg.preferred_factory_id or "").strip() != fid or cfg.work_mode != "fixed"):
            blockers.append("ana fabrikaya sabit değil")
        mission = _mission_label(name)
        rows.append(
            FleetAuditRow(
                account_name=name,
                ready=not blockers,
                blockers=blockers,
                mission=mission,
            )
        )
    return FleetAudit(total=len(rows), ready=sum(1 for r in rows if r.ready), rows=rows)


def format_fleet_audit_line(audit: FleetAudit) -> str:
    if audit.total <= 0:
        return "🧪 Otonomi audit: işçi hesap yok"
    icon = "🟢" if audit.ready == audit.total else "🟡"
    return f"{icon} Otonomi audit: {audit.ready}/{audit.total} işçi hazır"


def format_fleet_audit_blockers(audit: FleetAudit, *, limit: int = 5) -> str:
    rows = audit.blockers[:limit]
    if not rows:
        return ""
    lines = ["<b>Eksik otomasyon</b>"]
    for row in rows:
        lines.append(f"⚠️ <code>{row.account_name}</code> — {', '.join(row.blockers[:3])}")
    if len(audit.blockers) > limit:
        lines.append(f"<i>… +{len(audit.blockers) - limit} hesap</i>")
    return "\n".join(lines)
