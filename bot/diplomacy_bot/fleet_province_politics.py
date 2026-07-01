"""Province politics helpers for fleet missions."""

from __future__ import annotations

from typing import Any, Callable

from .game_api import api as game_api

ApiFn = Callable[..., tuple[int, Any]]


def _err_text(data: Any, st: int) -> str:
    if isinstance(data, dict):
        return str(data.get("error") or data.get("message") or f"HTTP {st}")[:80]
    return f"HTTP {st}"


def _pick_candidate(data: dict) -> str | None:
    elections = data.get("elections") or data.get("active") or []
    if isinstance(elections, dict):
        elections = list(elections.values())
    for el in elections:
        if not isinstance(el, dict) or el.get("voted") or el.get("has_voted"):
            continue
        cands = el.get("candidates") or el.get("nominees") or []
        if cands and isinstance(cands[0], dict):
            cid = cands[0].get("id") or cands[0].get("candidate_id")
            if cid:
                return str(cid)
    return None


def cast_province_election_vote(
    token: str,
    *,
    candidate_id: str | None = None,
    _api: ApiFn = game_api,
) -> dict:
    cid = (candidate_id or "").strip()
    if not cid:
        st, data = _api("GET", "/provinces/election", token, delay=0.2)
        if st != 200 or not isinstance(data, dict):
            return {"ok": False, "error": _err_text(data, st)}
        cid = _pick_candidate(data) or ""
    if not cid:
        return {"ok": False, "error": "oy verilecek aday yok"}
    st2, data2 = _api("POST", "/provinces/election/vote", token, {"candidate_id": cid}, delay=0.3)
    if st2 in (200, 201):
        return {"ok": True, "candidate_id": cid, "data": data2}
    return {"ok": False, "error": _err_text(data2, st2)}


def claim_independent_citizenship(
    token: str,
    province_name: str,
    *,
    _api: ApiFn = game_api,
) -> dict:
    prov = province_name.strip()
    if not prov:
        return {"ok": False, "error": "eyalet boş"}
    st, data = _api("POST", "/players/independent-citizenship", token, {"province_name": prov}, delay=0.3)
    if st in (200, 201):
        return {"ok": True, "province": prov, "data": data}
    return {"ok": False, "error": _err_text(data, st)}
