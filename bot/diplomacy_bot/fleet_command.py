"""Filo komuta — fabrika atama, bootstrap, toplu seyahat."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .account_config import get_config, save_config, update_config_field
from .account_main import get_main_account_name
from .account_runtime import account_context
from .auth import scoped_list_accounts
from .auto_defaults import AUTO_FEATURE_FIELDS
from .game_api import api as game_api
from .store import Account, get_account, set_autofarm

log = logging.getLogger(__name__)

DEFAULT_WORK_PROVINCE = "Hürmüz"


@dataclass
class FleetOpResult:
    account_name: str
    ok: bool
    message: str = ""


@dataclass
class FleetBatchResult:
    total: int = 0
    ok: int = 0
    results: list[FleetOpResult] = field(default_factory=list)

    def add(self, r: FleetOpResult) -> None:
        self.results.append(r)
        self.total += 1
        if r.ok:
            self.ok += 1


def _factory_id_from_dict(f: dict) -> str:
    return str(f.get("id") or f.get("factory_id") or "")


def lookup_factory_province(token: str, factory_id: str) -> str | None:
    """Fabrika UUID → eyalet adı (my + region taraması)."""
    fid = factory_id.strip()
    if not fid:
        return None
    for path in ("/factories/my", "/factories/region"):
        st, data = game_api("GET", path, token, delay=0.2)
        if st != 200 or not isinstance(data, dict):
            continue
        factories = data.get("factories") or data.get("data") or []
        if isinstance(factories, dict):
            factories = list(factories.values())
        for f in factories:
            if not isinstance(f, dict):
                continue
            if _factory_id_from_dict(f) == fid:
                prov = f.get("province_name") or f.get("region")
                if prov:
                    return str(prov)
    return None


def resolve_operator_factory(
    telegram_user_id: int,
    *,
    factory_id: str | None = None,
    main_account: str | None = None,
) -> tuple[str | None, str | None, str]:
    """(factory_uuid, province_name, error_message)"""
    if factory_id and factory_id.strip():
        fid = factory_id.strip()
        main = main_account or get_main_account_name(telegram_user_id)
        prov: str | None = None
        if main:
            acc = get_account(main)
            if acc:
                prov = lookup_factory_province(acc.token, fid)
        return fid, prov, ""

    main = main_account or get_main_account_name(telegram_user_id)
    if not main:
        return None, None, "Ana hesap yok — /setmain yap veya UUID ver"
    acc = get_account(main)
    if not acc:
        return None, None, f"Ana hesap `{main}` bulunamadı"
    cfg = get_config(main)
    fid = (cfg.primary_factory_id or cfg.preferred_factory_id or "").strip()
    if not fid:
        st, ws = game_api("GET", "/factories/work-status", acc.token, delay=0.15)
        if st == 200 and isinstance(ws, dict) and ws.get("working"):
            fid = str(ws.get("factory_id") or ws.get("current_factory_id") or "")
    if not fid:
        st, data = game_api("GET", "/factories/my", acc.token, delay=0.2)
        if st == 200 and isinstance(data, dict):
            owned = data.get("factories") or []
            if owned and isinstance(owned[0], dict):
                fid = _factory_id_from_dict(owned[0])
                if fid and not (cfg.primary_factory_id or "").strip():
                    update_config_field(
                        main,
                        primary_factory_id=fid,
                        preferred_factory_id=fid,
                    )
                    log.info("auto primary_factory_id %s → %s…", main, fid[:8])
    if not fid:
        return None, None, "Ana hesapta fabrika UUID bulunamadı — fabrika panelinden 🎯 işaretle"
    prov = lookup_factory_province(acc.token, fid)
    return fid, prov, ""


def assign_account_to_factory(
    acc: Account,
    factory_id: str,
    *,
    province: str | None = None,
) -> FleetOpResult:
    """Tek hesabı sabit fabrikaya bağla + isteğe bağlı seyahat."""
    from .modules import travel

    name = acc.name.strip().lower()
    fid = factory_id.strip()
    if not fid:
        return FleetOpResult(name, False, "fabrika UUID boş")

    update_config_field(
        name,
        work_mode="fixed",
        preferred_factory_id=fid,
        auto_travel_enabled=True,
    )

    travel_note = ""
    target_prov = (province or DEFAULT_WORK_PROVINCE).strip()
    try:
        with account_context(acc):
            if target_prov:
                tr = travel.ensure_in_province(acc.token, target_prov, leave_factory_first=True)
                if tr.get("ok"):
                    travel_note = f" → {target_prov}"
                elif tr.get("started"):
                    travel_note = f" · seyahat başladı ({target_prov})"
                elif tr.get("error") and "zaten" not in str(tr.get("error", "")).lower():
                    travel_note = f" · seyahat: {str(tr.get('error'))[:40]}"
    except Exception as e:
        travel_note = f" · seyahat hata: {str(e)[:40]}"

    return FleetOpResult(name, True, f"fixed `{fid[:8]}…`{travel_note}")


def assign_fleet_to_factory(
    telegram_user_id: int,
    *,
    factory_id: str | None = None,
    province: str | None = None,
    include_main: bool = False,
) -> FleetBatchResult:
    """Kullanıcının alt hesaplarını operatör fabrikasına bağla."""
    fid, auto_prov, err = resolve_operator_factory(telegram_user_id, factory_id=factory_id)
    if err or not fid:
        batch = FleetBatchResult()
        batch.add(FleetOpResult("-", False, err or "fabrika bulunamadı"))
        return batch

    prov = province or auto_prov or DEFAULT_WORK_PROVINCE
    main_name = (get_main_account_name(telegram_user_id) or "").strip().lower()
    batch = FleetBatchResult()
    for acc in scoped_list_accounts(telegram_user_id):
        if not include_main and main_name and acc.name == main_name:
            continue
        batch.add(assign_account_to_factory(acc, fid, province=prov))
    log.info("fleet_factory uid=%s fid=%s ok=%d/%d", telegram_user_id, fid[:8], batch.ok, batch.total)
    return batch


def travel_fleet(
    telegram_user_id: int,
    province_name: str,
    *,
    include_main: bool = True,
) -> FleetBatchResult:
    from .modules import travel

    target = province_name.strip()
    if not target:
        batch = FleetBatchResult()
        batch.add(FleetOpResult("-", False, "eyalet adı boş"))
        return batch

    main_name = (get_main_account_name(telegram_user_id) or "").strip().lower()
    batch = FleetBatchResult()
    for acc in scoped_list_accounts(telegram_user_id):
        if not include_main and main_name and acc.name == main_name:
            continue
        try:
            with account_context(acc):
                tr = travel.ensure_in_province(acc.token, target, leave_factory_first=True)
            if tr.get("ok") or tr.get("started"):
                msg = "vardı" if tr.get("ok") else f"seyahat ({tr.get('remaining_ms', 0)}ms)"
                batch.add(FleetOpResult(acc.name, True, msg))
            else:
                batch.add(FleetOpResult(acc.name, False, str(tr.get("error") or "seyahat başarısız")[:60]))
        except Exception as e:
            batch.add(FleetOpResult(acc.name, False, str(e)[:60]))
    return batch


def bulk_enable_auto(acc: Account) -> None:
    """Mevcut hesap için tüm oto bayrakları + autofarm."""
    set_autofarm(acc.name, True)
    cfg = get_config(acc.name)
    for fld in AUTO_FEATURE_FIELDS:
        if hasattr(cfg, fld):
            setattr(cfg, fld, True)
    save_config(cfg)


def bootstrap_fleet(
    telegram_user_id: int,
    *,
    role: str = "hybrid",
    limit: int | None = None,
    include_main: bool = False,
) -> FleetBatchResult:
    """İşçi hesaplara rol + autofarm + oto bayrakları."""
    from .account_config import normalize_role

    want = normalize_role(role)
    batch = FleetBatchResult()
    main_name = (get_main_account_name(telegram_user_id) or "").strip().lower()
    accs = scoped_list_accounts(telegram_user_id)
    if not include_main and main_name:
        accs = [a for a in accs if a.name.strip().lower() != main_name]
    if limit is not None:
        accs = accs[: max(0, limit)]
    if not accs:
        batch.add(FleetOpResult("-", False, "işçi hesap yok — önce token bağla"))
        return batch
    for acc in accs:
        try:
            update_config_field(acc.name, role=want)
            bulk_enable_auto(acc)
            batch.add(FleetOpResult(acc.name, True, f"rol={want} oto=açık"))
        except Exception as e:
            batch.add(FleetOpResult(acc.name, False, str(e)[:80]))
    return batch


def set_fleet_roles(
    telegram_user_id: int,
    role: str,
    *,
    limit: int | None = None,
) -> FleetBatchResult:
    from .account_config import normalize_role

    want = normalize_role(role)
    batch = FleetBatchResult()
    accs = scoped_list_accounts(telegram_user_id)
    if limit is not None:
        accs = accs[: max(0, limit)]
    for acc in accs:
        try:
            update_config_field(acc.name, role=want)
            batch.add(FleetOpResult(acc.name, True, want))
        except Exception as e:
            batch.add(FleetOpResult(acc.name, False, str(e)[:60]))
    return batch


def format_batch_html(title: str, batch: FleetBatchResult, *, footer: str = "") -> str:
    import html

    lines = [
        f"<b>{html.escape(title)}</b>",
        f"{batch.ok}/{batch.total} başarılı\n",
    ]
    for r in batch.results[:20]:
        icon = "✅" if r.ok else "❌"
        lines.append(f"{icon} <code>{html.escape(r.account_name)}</code> — {html.escape(r.message)}")
    if len(batch.results) > 20:
        lines.append(f"<i>… +{len(batch.results) - 20} hesap</i>")
    if footer:
        lines.append(f"\n{footer}")
    return "\n".join(lines)


from .fleet_status import (  # noqa: E402
    compute_fleet_next_steps,
    count_fleet_on_factory,
    format_factory_capacity_line,
    format_fleet_ops_status,
    format_next_steps_footer,
)
