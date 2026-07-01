"""Filo bölge operasyonları — ikamet, seçim oyu, vatandaşlık/vize."""

from __future__ import annotations

import logging
from typing import Any, Callable

from .account_main import get_main_account_name
from .account_runtime import account_context
from .auth import scoped_list_accounts
from .fleet_command import (
    FleetBatchResult,
    FleetOpResult,
    assign_fleet_to_factory,
    resolve_operator_factory,
    travel_fleet,
)
from .game_api import api as game_api, get_profile
from .store import Account, get_account

log = logging.getLogger(__name__)

ApiFn = Callable[..., tuple[int, Any]]

DEFAULT_RESIDENCE_PROVINCE = "Hürmüz"


def _err_text(data: Any, st: int) -> str:
    if isinstance(data, dict):
        return str(data.get("error") or data.get("message") or f"HTTP {st}")[:80]
    return f"HTTP {st}"


def get_residence_info(token: str, *, _api: ApiFn = game_api) -> dict:
    st, data = _api("GET", "/players/residence", token, delay=0.2)
    if st != 200 or not isinstance(data, dict):
        return {"ok": False, "error": _err_text(data, st)}
    return {"ok": True, **data}


def set_residence(
    token: str,
    province_name: str,
    *,
    _api: ApiFn = game_api,
) -> dict:
    """İkamet eyaleti ayarla — province_name ve province_id fallback, PUT→POST."""
    prov = province_name.strip()
    bodies: list[dict] = [{"province_name": prov}]
    try:
        from .modules import travel

        found = travel.find_province_by_name(travel.list_provinces(token, _api=_api), prov)
        if found:
            pid = found.get("id") or found.get("province_id")
            if pid is not None:
                alt = {"province_name": prov, "province_id": pid}
                if alt not in bodies:
                    bodies.append(alt)
    except Exception:
        pass

    last_st, last_data = 400, {}
    for body in bodies:
        for method in ("PUT", "POST"):
            st, data = _api(method, "/players/residence", token, body, delay=0.25)
            last_st, last_data = st, data
            if st in (200, 201):
                return {"ok": True, "province": prov, "method": method, "data": data}
    return {"ok": False, "error": _err_text(last_data, last_st)}


def set_account_residence(acc: Account, province_name: str) -> FleetOpResult:
    name = acc.name.strip().lower()
    prov = province_name.strip()
    if not prov:
        return FleetOpResult(name, False, "eyalet boş")
    try:
        with account_context(acc):
            info = get_residence_info(acc.token)
            current = (info.get("residence_province") or info.get("province") or "").strip()
            if current and current.lower() == prov.lower():
                return FleetOpResult(name, True, f"ikamet zaten {current}")
            r = set_residence(acc.token, prov)
        if r.get("ok"):
            return FleetOpResult(name, True, f"ikamet → {prov}")
        return FleetOpResult(name, False, str(r.get("error") or "ikamet başarısız"))
    except Exception as e:
        return FleetOpResult(name, False, str(e)[:80])


def set_fleet_residence(telegram_user_id: int, province_name: str) -> FleetBatchResult:
    batch = FleetBatchResult()
    for acc in scoped_list_accounts(telegram_user_id):
        batch.add(set_account_residence(acc, province_name))
    log.info("fleet_residence uid=%s prov=%s ok=%d/%d", telegram_user_id, province_name, batch.ok, batch.total)
    return batch


def _pick_vote_targets(data: dict, candidate_id: str | None) -> tuple[str | None, str | None]:
    elections = data.get("elections") or data.get("active") or []
    if isinstance(elections, dict):
        elections = list(elections.values())
    for el in elections:
        if not isinstance(el, dict):
            continue
        if el.get("voted") or el.get("has_voted"):
            continue
        eid = str(el.get("id") or el.get("election_id") or "")
        if candidate_id:
            return (eid or None), candidate_id
        cands = el.get("candidates") or el.get("nominees") or []
        if cands and isinstance(cands[0], dict):
            cid = str(cands[0].get("id") or cands[0].get("candidate_id") or "")
            if cid:
                return (eid or None), cid
    return None, None


def cast_election_vote(
    token: str,
    *,
    election_id: str | None = None,
    candidate_id: str | None = None,
    _api: ApiFn = game_api,
) -> dict:
    st, data = _api("GET", "/elections/active", token, delay=0.2)
    if st != 200 or not isinstance(data, dict):
        return {"ok": False, "error": _err_text(data, st)}
    eid, cid = election_id, candidate_id
    if not cid:
        eid, cid = _pick_vote_targets(data, None)
    if not cid:
        return {"ok": False, "error": "oy verilecek aday yok"}
    body: dict[str, str] = {"candidate_id": cid}
    if eid:
        body["election_id"] = eid
    st2, data2 = _api("POST", "/elections/vote", token, body, delay=0.3)
    if st2 in (200, 201):
        return {"ok": True, "candidate_id": cid, "election_id": eid, "data": data2}
    return {"ok": False, "error": _err_text(data2, st2)}


def vote_account(acc: Account, *, candidate_id: str | None = None) -> FleetOpResult:
    name = acc.name.strip().lower()
    try:
        with account_context(acc):
            r = cast_election_vote(acc.token, candidate_id=candidate_id)
        if r.get("ok"):
            cid = (r.get("candidate_id") or "")[:8]
            return FleetOpResult(name, True, f"oy → {cid}…")
        return FleetOpResult(name, False, str(r.get("error") or "oy başarısız"))
    except Exception as e:
        return FleetOpResult(name, False, str(e)[:80])


def fleet_vote(telegram_user_id: int, *, candidate_id: str | None = None) -> FleetBatchResult:
    batch = FleetBatchResult()
    for acc in scoped_list_accounts(telegram_user_id):
        batch.add(vote_account(acc, candidate_id=candidate_id))
    return batch


def get_citizenship_info(token: str, *, _api: ApiFn = game_api) -> dict:
    st, data = _api("GET", "/citizenship/my", token, delay=0.2)
    if st != 200 or not isinstance(data, dict):
        return {"ok": False, "error": _err_text(data, st)}
    return {"ok": True, **data}


def apply_citizenship(
    token: str,
    country_id: str,
    *,
    reason: str = "Filo operasyonu",
    _api: ApiFn = game_api,
) -> dict:
    body = {"to_country_id": str(country_id), "reason": reason[:120]}
    st, data = _api("POST", "/citizenship/apply", token, body, delay=0.3)
    if st in (200, 201):
        return {"ok": True, "data": data}
    return {"ok": False, "error": _err_text(data, st)}


def resolve_operator_country_id(telegram_user_id: int) -> str | None:
    main = get_main_account_name(telegram_user_id)
    if not main or not (acc := get_account(main)):
        return None
    try:
        with account_context(acc):
            prof = get_profile(acc.token)
        return str(prof.country_id) if prof.country_id else None
    except Exception:
        return None


def apply_account_citizenship(acc: Account, country_id: str) -> FleetOpResult:
    name = acc.name.strip().lower()
    cid = str(country_id).strip()
    if not cid:
        return FleetOpResult(name, False, "ülke id boş")
    try:
        with account_context(acc):
            info = get_citizenship_info(acc.token)
            status = str(info.get("status") or "").lower()
            if status in ("citizen", "approved", "active"):
                return FleetOpResult(name, True, "zaten vatandaş")
            r = apply_citizenship(acc.token, cid)
        if r.get("ok"):
            return FleetOpResult(name, True, f"başvuru → {cid[:8]}")
        return FleetOpResult(name, False, str(r.get("error") or "başvuru başarısız"))
    except Exception as e:
        return FleetOpResult(name, False, str(e)[:80])


def fleet_citizenship_apply(
    telegram_user_id: int,
    country_id: str | None = None,
) -> FleetBatchResult:
    cid = (country_id or resolve_operator_country_id(telegram_user_id) or "").strip()
    batch = FleetBatchResult()
    if not cid:
        batch.add(FleetOpResult("-", False, "ülke id yok — /fleetcitizen <id> veya ana hesap ülkesi"))
        return batch
    for acc in scoped_list_accounts(telegram_user_id):
        batch.add(apply_account_citizenship(acc, cid))
    return batch


def get_visa_summary(token: str, *, _api: ApiFn = game_api) -> dict:
    st, data = _api("GET", "/visas/my", token, delay=0.2)
    if st == 200 and isinstance(data, dict):
        return {"ok": True, **data}
    st2, data2 = _api("GET", "/visas/pending-count", token, delay=0.15)
    if st2 == 200 and isinstance(data2, dict):
        return {"ok": True, "pending_count": data2.get("count", 0)}
    return {"ok": False, "error": _err_text(data2, st2)}


def apply_visa(
    token: str,
    country_id: str,
    *,
    reason: str = "Filo operasyonu",
    _api: ApiFn = game_api,
) -> dict:
    body = {"to_country_id": str(country_id), "reason": reason[:120]}
    st, data = _api("POST", "/visas/apply", token, body, delay=0.3)
    if st in (200, 201):
        return {"ok": True, "data": data}
    return {"ok": False, "error": _err_text(data, st)}


def apply_account_visa(acc: Account, country_id: str) -> FleetOpResult:
    name = acc.name.strip().lower()
    cid = str(country_id).strip()
    if not cid:
        return FleetOpResult(name, False, "ülke id boş")
    try:
        with account_context(acc):
            r = apply_visa(acc.token, cid)
        if r.get("ok"):
            return FleetOpResult(name, True, f"vize → {cid[:8]}")
        return FleetOpResult(name, False, str(r.get("error") or "vize başarısız"))
    except Exception as e:
        return FleetOpResult(name, False, str(e)[:80])


def fleet_visa_apply(telegram_user_id: int, country_id: str | None = None) -> FleetBatchResult:
    cid = (country_id or resolve_operator_country_id(telegram_user_id) or "").strip()
    batch = FleetBatchResult()
    if not cid:
        batch.add(FleetOpResult("-", False, "ülke id yok"))
        return batch
    for acc in scoped_list_accounts(telegram_user_id):
        batch.add(apply_account_visa(acc, cid))
    return batch


from .fleet_aod_setup import run_aod_setup  # noqa: E402 — re-export
