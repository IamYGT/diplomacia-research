"""Günlük ödül + görev claim — orchestrator tick başı (idempotent)."""

from __future__ import annotations

import logging
from typing import Any, Callable

log = logging.getLogger(__name__)

ApiFn = Callable[..., tuple[int, Any]]
_DAILY_KEY_HINTS = ("daily", "gunluk", "günlük")


def infer_daily_from_quests(quests: list[dict]) -> dict[str, bool | None]:
    """Quest listesinden günlük ödül durumu — ek API yok."""
    for q in quests:
        key = str(q.get("quest_key") or "").lower()
        if not any(h in key for h in _DAILY_KEY_HINTS):
            continue
        if q.get("rewarded"):
            return {"daily_claimed": True, "daily_available": False}
        prog = int(q.get("progress") or 0)
        target = int(q.get("target") or 0)
        if target > 0 and prog >= target:
            return {"daily_claimed": False, "daily_available": True}
        return {"daily_claimed": False, "daily_available": False}
    return {"daily_claimed": None, "daily_available": True}


def _already_claimed_message(data: Any, status: int) -> bool:
    if status == 200 and isinstance(data, dict):
        if data.get("already_claimed") or data.get("claimed") is False and "reward" not in data:
            msg = str(data.get("message") or data.get("error") or "").lower()
            return "zaten" in msg or "already" in msg
    msg = str((data or {}).get("error") or (data or {}).get("message") or "").lower()
    if status in (400, 409) and ("zaten" in msg or "already" in msg or "bugün" in msg):
        return True
    return False


def try_daily_claim(token: str, *, _api: ApiFn | None = None) -> dict[str, Any]:
    from .game_api import api as default_api

    api = _api or default_api
    st, data = api("POST", "/players/daily-claim", token, {}, delay=0.5)
    if st == 200 and isinstance(data, dict):
        if data.get("claimed") or data.get("daily_reward") or data.get("reward"):
            reward = data.get("reward") or data.get("daily_reward") or {}
            return {"ok": True, "claimed": True, "reward": reward, "data": data}
        if _already_claimed_message(data, st):
            return {"ok": False, "already_claimed": True}
    if _already_claimed_message(data, st):
        return {"ok": False, "already_claimed": True}
    err = ""
    if isinstance(data, dict):
        err = str(data.get("error") or data.get("message") or f"HTTP {st}")
    return {"ok": False, "error": err or f"HTTP {st}", "status": st}


def try_quest_claims(token: str, *, _api: ApiFn | None = None) -> dict[str, Any]:
    from .game_api import claim_ready_quests

    try:
        results = claim_ready_quests(token)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "results": []}
    ok_n = sum(1 for r in results if r.get("ok"))
    return {"ok": ok_n > 0, "claimed_count": ok_n, "results": results}


def run_routine_claims(
    token: str,
    cfg,
    *,
    _api: ApiFn | None = None,
) -> dict[str, Any]:
    """Tick başı rutin — config flag'lerine göre."""
    out: dict[str, Any] = {}
    if getattr(cfg, "auto_daily_claim", True):
        daily = try_daily_claim(token, _api=_api)
        out["daily"] = daily
        if daily.get("claimed"):
            log.info("routine daily_claim ok")
        elif daily.get("already_claimed"):
            log.debug("routine daily already claimed")
    if getattr(cfg, "auto_quest_claim", True):
        quests = try_quest_claims(token, _api=_api)
        if quests.get("claimed_count"):
            out["quests"] = quests
            log.info("routine quest_claim count=%s", quests.get("claimed_count"))
        elif quests.get("results") is not None and not quests.get("error"):
            out["quests"] = quests
    return out
