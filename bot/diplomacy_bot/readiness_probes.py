"""Readiness probe — dashboard + ek menü ortak katman."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .account_config import get_config
from .store import Account
from .feature_analysis import (
    analyze_auto_status,
    analyze_craft,
    analyze_passive,
    analyze_quests,
    analyze_training,
    analyze_wars,
    build_readiness,
)
from .game_api import api as default_api, get_profile, get_quests
from .modules import economy, stats as stats_mod, training

READINESS_CACHE_SEC = float(os.environ.get("READINESS_CACHE_SEC", "60"))


def auto_raw_from_row(row: dict) -> dict:
    return {
        "next_work_in_ms": int(row.get("work_wait_ms") or row.get("work_ms") or 0),
        "pill_cooldown_ms": int(row.get("pill_cooldown_ms") or row.get("pill_ms") or 0),
        "free_attack_available": bool(row.get("free_attack")),
        "free_attack_cooldown_ms": int(row.get("free_attack_cooldown_ms") or 0),
        "auto_work_active": bool(row.get("auto_work_active")),
        "auto_war_active": bool(row.get("auto_war_active")),
        "health": int(row.get("health") or 0),
        "health_pills": int(row.get("pills") or 0),
    }


def analyze_from_snapshot_row(row: dict, cfg) -> dict[str, dict]:
    auto_raw = auto_raw_from_row(row)
    profile_h = int(row.get("health") or 0)
    return {
        "auto": analyze_auto_status(auto_raw, profile_health=profile_h),
        "passive": analyze_passive(
            {"available_points": row.get("passive_available"), "passive_skills": {}},
            cfg,
            row.get("class"),
        ),
        "craft": analyze_craft(
            {"diamonds": row.get("diamonds"), "health_pills": row.get("pills")},
            auto_raw,
            cfg,
        ),
    }


def _run_with_account_ctx(acc: Account | None, fn: Callable[[], dict]) -> dict:
    if acc is None:
        try:
            return fn()
        except Exception:
            return {}
    from .account_runtime import interactive_account_context

    with interactive_account_context(acc):
        try:
            return fn()
        except Exception:
            return {}


def probe_readiness_light(
    token: str,
    account_name: str,
    row: dict,
    *,
    api_delay: float = 0.08,
    _api: Callable | None = None,
    acc: Account | None = None,
) -> dict[str, dict]:
    """Dashboard — snapshot'tan local + 3 hafif ağ probe (paralel)."""
    api = _api or default_api
    cfg = get_config(account_name)
    auto_raw = auto_raw_from_row(row)
    out = analyze_from_snapshot_row(row, cfg)

    parallel = os.environ.get("READINESS_PARALLEL", "1").strip().lower() in ("1", "true", "yes", "on")

    def quests_probe() -> dict:
        return analyze_quests(get_quests(token))

    def training_probe() -> dict:
        return analyze_training(auto_raw, training.get_my_training_war(token))

    def wars_probe() -> dict:
        st, d = api("GET", "/wars/my-country", token, delay=api_delay)
        return analyze_wars(d if st == 200 and isinstance(d, dict) else {}, cfg)

    if parallel:
        with ThreadPoolExecutor(max_workers=3) as pool:
            out["quests"] = pool.submit(_run_with_account_ctx, acc, quests_probe).result()
            out["training"] = pool.submit(_run_with_account_ctx, acc, training_probe).result()
            out["wars"] = pool.submit(_run_with_account_ctx, acc, wars_probe).result()
    else:
        out["quests"] = _run_with_account_ctx(acc, quests_probe)
        out["training"] = _run_with_account_ctx(acc, training_probe)
        out["wars"] = _run_with_account_ctx(acc, wars_probe)
    return out


def probe_readiness_full(token: str, account_name: str, *, api_delay: float = 0.15) -> dict[str, dict]:
    """Ek menü — 6 paralel probe."""
    cfg = get_config(account_name)

    def q():
        try:
            return analyze_quests(get_quests(token))
        except Exception:
            return {}

    def a():
        from .health_sync import analyze_auto_with_profile

        return analyze_auto_with_profile(token)

    def w():
        try:
            st, d = default_api("GET", "/wars/my-country", token, delay=api_delay)
            return analyze_wars(d if st == 200 and isinstance(d, dict) else {}, cfg)
        except Exception:
            return {}

    def p():
        try:
            return analyze_passive(stats_mod.get_passive_skills(token), cfg)
        except Exception:
            return {}

    def c():
        try:
            prof = get_profile(token)
            auto = economy.get_auto_status(token) or {}
            return analyze_craft(
                {"diamonds": prof.diamonds, "health_pills": prof.health_pills}, auto, cfg
            )
        except Exception:
            return {}

    def t(auto_raw):
        try:
            return analyze_training(auto_raw, training.get_my_training_war(token))
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        aa = pool.submit(a).result()
        auto_raw = {
            "next_work_in_ms": aa.get("work_ms", 0),
            "free_attack_available": aa.get("free_attack"),
            "free_attack_cooldown_ms": aa.get("attack_ms", 0),
            "health_pills": aa.get("pills", 0),
        }
        return {
            "quests": pool.submit(q).result(),
            "auto": aa,
            "wars": pool.submit(w).result(),
            "passive": pool.submit(p).result(),
            "craft": pool.submit(c).result(),
            "training": pool.submit(t, auto_raw).result(),
        }


def build_readiness_from_probes(probes: dict[str, dict]) -> dict[str, Any]:
    from .routine_claims import infer_daily_from_quests

    qa = probes.get("quests") or {}
    all_quests = list(qa.get("claimable") or []) + list(qa.get("in_progress") or []) + list(qa.get("done") or [])
    readiness = build_readiness(
        quests_analysis=qa,
        auto_analysis=probes.get("auto") or {},
        wars_analysis=probes.get("wars") or {},
        passive_analysis=probes.get("passive") or {},
        craft_analysis=probes.get("craft") or {},
        training_analysis=probes.get("training") or {},
    )
    readiness["daily"] = infer_daily_from_quests(all_quests)
    return readiness


def readiness_fields(readiness: dict[str, Any]) -> dict[str, Any]:
    daily = readiness.get("daily") or {}
    return {
        "quests_claimable": int(readiness.get("quest_claimable") or 0),
        "training_ready": bool(readiness.get("training_ready")),
        "craft_ready": bool(readiness.get("craft_ready")),
        "war_active": int(readiness.get("war_active") or 0),
        "readiness_highlights": list(readiness.get("highlights") or [])[:4],
        "daily_claimed": daily.get("daily_claimed"),
        "daily_available": bool(daily.get("daily_available")),
    }


def fetch_readiness_pack(token: str, account_name: str) -> dict[str, Any]:
    probes = probe_readiness_full(token, account_name)
    readiness = build_readiness_from_probes(probes)
    return {"ok": True, "readiness": readiness, **probes}
