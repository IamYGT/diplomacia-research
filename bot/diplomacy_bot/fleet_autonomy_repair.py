"""Fleet autonomy repair — make worker accounts match unattended defaults."""

from __future__ import annotations

from .account_config import normalize_role, update_config_field
from .account_main import get_main_account_name
from .auth import scoped_list_accounts
from .fleet_command import FleetBatchResult, FleetOpResult, resolve_operator_factory
from .store import set_autofarm


def repair_fleet_autonomy_for_uid(
    telegram_user_id: int,
    *,
    role: str = "hybrid",
    factory_id: str | None = None,
) -> FleetBatchResult:
    """Enable farm/stat/training/craft/travel and fixed factory for worker accounts."""
    batch = FleetBatchResult()
    fid, _prov, err = resolve_operator_factory(telegram_user_id, factory_id=factory_id)
    if err or not fid:
        batch.add(FleetOpResult("-", False, err or "fabrika bulunamadı"))
        return batch

    main = (get_main_account_name(telegram_user_id) or "").strip().lower()
    want_role = normalize_role(role)
    for acc in scoped_list_accounts(telegram_user_id):
        name = acc.name.strip().lower()
        if main and name == main:
            continue
        try:
            set_autofarm(name, True)
            update_config_field(
                name,
                role=want_role,
                work_mode="fixed",
                preferred_factory_id=fid,
                stat_auto_enabled=True,
                training_enabled=True,
                craft_pills_when_low=True,
                auto_travel_enabled=True,
                auto_token_refresh=True,
            )
            batch.add(FleetOpResult(name, True, f"ready role={want_role} factory={fid[:8]}…"))
        except Exception as e:
            batch.add(FleetOpResult(name, False, str(e)[:80]))
    if batch.total == 0:
        batch.add(FleetOpResult("-", False, "işçi hesap yok"))
    return batch
