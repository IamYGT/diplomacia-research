"""Kayıtlı API yollarını canlı veya mock ortamda sırayla dener."""
from __future__ import annotations

import time
from typing import Any, Callable

from .api_route_contract import ContractError, validate_response
from .api_route_registry import BOT_API_ROUTES, ApiRouteSpec, safe_probe_routes
from .game_client import normalize_path

ApiFn = Callable[..., tuple[int, Any]]


def _first_id(items: list[dict], *keys: str) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        for k in keys:
            v = item.get(k)
            if v is not None and str(v).strip():
                return str(v)
    return None


def build_probe_context(api_fn: ApiFn, token: str, *, delay: float = 0.15) -> dict[str, Any]:
    """Parametreli route'lar için örnek id'ler topla."""
    ctx: dict[str, Any] = {}
    st, prof = api_fn("GET", "/players/profile", token, delay=delay)
    if st == 200 and isinstance(prof, dict):
        ctx["profile"] = prof
        pid = prof.get("id") or prof.get("player_id")
        if pid:
            ctx["player_id"] = str(pid)

    st, wars = api_fn("GET", "/wars/my-country", token, delay=delay)
    if st == 200 and isinstance(wars, dict):
        wl = wars.get("wars") or []
        if isinstance(wl, list):
            wid = _first_id(wl, "id", "war_id")
            if wid:
                ctx["war_id"] = wid

    st, tw = api_fn("GET", "/training-wars/my", token, delay=delay)
    if st == 200 and isinstance(tw, dict) and tw.get("id"):
        ctx["training_war_id"] = str(tw["id"])

    st, fac = api_fn("GET", "/factories/my", token, delay=delay)
    if st == 200 and isinstance(fac, dict):
        fl = fac.get("factories") or []
        if isinstance(fl, list):
            fid = _first_id(fl, "id", "factory_id")
            if fid:
                ctx["factory_id"] = fid

    st, quests = api_fn("GET", "/quests", token, delay=delay)
    if st == 200 and isinstance(quests, dict):
        ql = quests.get("quests") or []
        if isinstance(ql, list):
            for q in ql:
                if isinstance(q, dict) and q.get("claimable"):
                    key = q.get("key") or q.get("id")
                    if key:
                        ctx["quest_key"] = str(key)
                        break

    return ctx


def resolve_path(spec: ApiRouteSpec, ctx: dict[str, Any]) -> str:
    path = spec.path
    if "{id}" not in path:
        return path
    src = spec.path_params_from or "war_id"
    val = ctx.get(src) or ctx.get("war_id") or ctx.get("training_war_id") or "0"
    return normalize_path(path, {"id": str(val)})


def resolve_body(spec: ApiRouteSpec, ctx: dict[str, Any]) -> dict | None:
    if spec.body is None:
        return None
    body = dict(spec.body)
    fid = ctx.get("factory_id")
    if fid:
        for k in ("factory_id",):
            if k in body and not body[k]:
                body[k] = fid
    return body


def probe_route(
    spec: ApiRouteSpec,
    api_fn: ApiFn,
    token: str,
    ctx: dict[str, Any],
    *,
    delay: float = 0.12,
    run_mutating: bool = False,
    include_data: bool = False,
) -> dict[str, Any]:
    if not spec.safe_probe and not run_mutating:
        return {
            "route_id": spec.route_id,
            "skipped": True,
            "reason": "mutating",
            "method": spec.method,
            "path": spec.path,
        }

    path = resolve_path(spec, ctx)
    if "{id}" in spec.path and path.endswith("/0") and spec.path_params_from:
        return {
            "route_id": spec.route_id,
            "skipped": True,
            "reason": f"missing context:{spec.path_params_from}",
            "method": spec.method,
            "path": spec.path,
        }

    body = resolve_body(spec, ctx)
    t0 = time.time()
    try:
        status, data = api_fn(spec.method, path, token, body, delay=delay)
    except Exception as exc:
        return {
            "route_id": spec.route_id,
            "ok": False,
            "error": str(exc)[:200],
            "method": spec.method,
            "path": path,
            "elapsed_ms": int((time.time() - t0) * 1000),
        }

    out: dict[str, Any] = {
        "route_id": spec.route_id,
        "method": spec.method,
        "path": path,
        "status": status,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "data_keys": list(data.keys())[:16] if isinstance(data, dict) else type(data).__name__,
    }
    if include_data:
        out["data"] = data
    try:
        validate_response(spec, status, data)
        out["ok"] = True
        out["contract"] = "pass"
    except ContractError as e:
        out["ok"] = False
        out["contract"] = "fail"
        out["contract_error"] = str(e)
    return out


def run_probe_suite(
    api_fn: ApiFn,
    token: str,
    *,
    safe_only: bool = True,
    delay: float = 0.12,
    include_data: bool = False,
) -> dict[str, Any]:
    ctx = build_probe_context(api_fn, token, delay=delay)
    routes = safe_probe_routes() if safe_only else list(BOT_API_ROUTES)
    results: list[dict[str, Any]] = []
    for spec in routes:
        results.append(
            probe_route(
                spec,
                api_fn,
                token,
                ctx,
                delay=delay,
                run_mutating=not safe_only,
                include_data=include_data,
            )
        )
    passed = sum(1 for r in results if r.get("ok"))
    failed = [r for r in results if r.get("contract") == "fail" or r.get("error")]
    skipped = sum(1 for r in results if r.get("skipped"))
    return {
        "ok": len(failed) == 0,
        "passed": passed,
        "failed_count": len(failed),
        "skipped": skipped,
        "total": len(results),
        "context_keys": list(ctx.keys()),
        "results": results,
        "failures": failed,
    }
