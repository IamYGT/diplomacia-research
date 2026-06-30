"""Kayıtlı API yanıtları (cassette) — mutating route'lar CI'da canlı çağrı olmadan doğrulanır."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .api_route_contract import ContractError, validate_response
from .api_route_probe import build_probe_context, probe_route, resolve_path
from .api_route_registry import BOT_API_ROUTES, ApiRouteSpec

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
DEFAULT_CASSETTE = _FIXTURES_DIR / "api_replay.json"
LEGACY_CONTRACTS = _FIXTURES_DIR / "api_contracts.json"

ApiFn = Callable[..., tuple[int, Any]]


def load_cassette(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_CASSETTE
    if not p.exists():
        raise FileNotFoundError(f"cassette yok: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _merge_legacy_samples(cassette: dict[str, Any]) -> dict[str, Any]:
    """api_contracts.json örneklerini cassette'e yedekle (eksik route_id)."""
    if not LEGACY_CONTRACTS.exists():
        return cassette
    legacy = json.loads(LEGACY_CONTRACTS.read_text(encoding="utf-8"))
    by_id = {r["route_id"]: r for r in cassette.get("replays", [])}
    for sample in legacy.get("samples", []):
        rid = sample["route_id"]
        if rid not in by_id:
            by_id[rid] = {
                "route_id": rid,
                "status": sample["status"],
                "data": sample["data"],
            }
    out = dict(cassette)
    out["replays"] = list(by_id.values())
    return out


def replay_index(cassette: dict[str, Any]) -> dict[str, dict[str, Any]]:
    merged = _merge_legacy_samples(cassette)
    return {r["route_id"]: r for r in merged.get("replays", [])}


def default_context(cassette: dict[str, Any]) -> dict[str, Any]:
    merged = _merge_legacy_samples(cassette)
    return dict(merged.get("default_context") or {})


def make_replay_api_fn(
    cassette: dict[str, Any],
    *,
    route_calls: list[tuple[str, str, str]] | None = None,
) -> ApiFn:
    """route_id eşlemesi için probe_route'un çağırdığı path'e göre cassette döner."""
    idx = replay_index(cassette)
    by_path: dict[tuple[str, str], tuple[int, Any]] = {}
    ctx = default_context(cassette)
    for spec in BOT_API_ROUTES:
        entry = idx.get(spec.route_id)
        if not entry:
            continue
        path = resolve_path(spec, ctx) if "{id}" in spec.path else spec.path
        by_path[(spec.method, path)] = (int(entry["status"]), entry.get("data"))

    def _api(method: str, path: str, token: str, body=None, delay: float = 0):
        if route_calls is not None:
            route_calls.append((method, path, token))
        key = (method.upper(), path.split("?")[0])
        if key in by_path:
            return by_path[key]
        # context toplama çağrıları — cassette'teki safe route yanıtları
        for spec in BOT_API_ROUTES:
            p = resolve_path(spec, ctx) if "{id}" in spec.path else spec.path
            if spec.method == method.upper() and p.split("?")[0] == key[1]:
                ent = idx.get(spec.route_id)
                if ent:
                    return int(ent["status"]), ent.get("data")
        return 404, {"error": "replay miss", "path": path}

    return _api


def routes_missing_replay(cassette: dict[str, Any]) -> list[str]:
    idx = replay_index(cassette)
    return [r.route_id for r in BOT_API_ROUTES if r.route_id not in idx]


def validate_cassette_contracts(cassette: dict[str, Any]) -> list[dict[str, Any]]:
    """Her replay kaydının sözleşmeyi geçip geçmediğini doğrula."""
    idx = replay_index(cassette)
    by_id = {r.route_id: r for r in BOT_API_ROUTES}
    failures: list[dict[str, Any]] = []
    for rid, entry in idx.items():
        spec = by_id.get(rid)
        if not spec:
            failures.append({"route_id": rid, "error": "bilinmeyen route_id"})
            continue
        try:
            validate_response(spec, int(entry["status"]), entry.get("data"))
        except ContractError as e:
            failures.append({"route_id": rid, "error": str(e)})
    return failures


def run_replay_suite(cassette: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tüm route'lar — cassette yanıtı + probe_route path çözümlemesi."""
    cassette = cassette or load_cassette()
    missing = routes_missing_replay(cassette)
    missing_ids = set(missing)  # routes_missing_replay route_id string listesi döndürür
    contract_fails = validate_cassette_contracts(cassette)
    ctx = default_context(cassette)
    calls: list[tuple[str, str, str]] = []
    api_fn = make_replay_api_fn(cassette, route_calls=calls)
    results: list[dict[str, Any]] = []
    for spec in BOT_API_ROUTES:
        if spec.route_id in missing_ids:
            results.append(
                {
                    "route_id": spec.route_id,
                    "ok": False,
                    "replay": "missing",
                }
            )
            continue
        out = probe_route(spec, api_fn, "replay-token", ctx, delay=0, run_mutating=True)
        out["replay"] = "ok" if out.get("ok") else "fail"
        results.append(out)
    failed = [r for r in results if not r.get("ok")]
    return {
        "ok": not missing and not contract_fails and not failed,
        "missing_replay": missing,
        "contract_failures": contract_fails,
        "passed": sum(1 for r in results if r.get("ok")),
        "total": len(BOT_API_ROUTES),
        "results": results,
        "failures": failed,
    }


def compare_catalog_vs_registry(
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    """bot registry yollarının api_catalog.json'da karşılığı var mı."""
    from .api_route_registry import normalize_route_path, registry_keys

    cat_path = catalog_path or (Path(__file__).resolve().parents[1] / "data" / "api_catalog.json")
    if not cat_path.exists():
        return {"ok": True, "skipped": True, "reason": f"katalog yok: {cat_path}"}

    raw = json.loads(cat_path.read_text(encoding="utf-8"))
    catalog_keys: set[tuple[str, str]] = set()
    catalog_paths: set[str] = set()
    for ep in raw.get("endpoints", []):
        method = ep["method"].upper()
        path = ep["path"].split("?")[0]
        path = normalize_route_path(path)
        catalog_keys.add((method, path))
        catalog_paths.add(path)

    bot_keys = registry_keys()
    missing_in_catalog: list[dict[str, str]] = []
    method_mismatch: list[dict[str, str]] = []
    for method, path in sorted(bot_keys):
        if (method, path) in catalog_keys:
            continue
        if path in catalog_paths:
            method_mismatch.append({"method": method, "path": path, "note": "catalog farklı HTTP method"})
            continue
        missing_in_catalog.append({"method": method, "path": path})

    extra_in_bot = len(missing_in_catalog)
    return {
        "ok": extra_in_bot == 0,
        "catalog_path": str(cat_path),
        "bot_route_count": len(bot_keys),
        "catalog_route_count": len(catalog_keys),
        "missing_in_catalog": missing_in_catalog,
        "method_mismatch": method_mismatch,
    }


_MAX_LIST = 8
_MAX_STR = 400
_MAX_DEPTH = 4


def _sanitize_value(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return "…"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if value.startswith("eyJ") and len(value) > 40:
            return "<redacted-jwt>"
        return value[:_MAX_STR] + ("…" if len(value) > _MAX_STR else "")
    if isinstance(value, list):
        return [_sanitize_value(v, depth + 1) for v in value[:_MAX_LIST]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in list(value.items())[:32]:
            lk = str(k).lower()
            if lk in ("token", "password", "authorization", "refresh_token"):
                out[k] = "<redacted>"
            else:
                out[k] = _sanitize_value(v, depth + 1)
        return out
    return str(value)[:_MAX_STR]


def context_for_cassette(ctx: dict[str, Any]) -> dict[str, str]:
    keys = ("war_id", "factory_id", "quest_key", "training_war_id", "player_id")
    return {k: str(ctx[k]) for k in keys if ctx.get(k)}


def save_cassette(cassette: dict[str, Any], path: Path | None = None) -> Path:
    p = path or DEFAULT_CASSETTE
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cassette, ensure_ascii=False, indent=2)
    p.write_text(text + "\n", encoding="utf-8")
    return p


def record_cassette_from_live(
    api_fn: ApiFn,
    token: str,
    *,
    include_mutating: bool = False,
    delay: float = 0.12,
    cassette_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Canlı API yanıtlarını cassette'e yazar; mevcut kayıtları route_id bazında birleştirir."""
    path = cassette_path or DEFAULT_CASSETTE
    existing = load_cassette(path) if path.exists() else {"meta": {"version": 1}, "default_context": {}, "replays": []}
    by_id = {r["route_id"]: r for r in existing.get("replays", [])}

    ctx = build_probe_context(api_fn, token, delay=delay)
    new_context = {**existing.get("default_context", {}), **context_for_cassette(ctx)}

    recorded: list[str] = []
    skipped: list[str] = []
    contract_fails: list[dict[str, Any]] = []

    for spec in BOT_API_ROUTES:
        if not spec.safe_probe and not include_mutating:
            skipped.append(spec.route_id)
            continue
        out = probe_route(
            spec,
            api_fn,
            token,
            ctx,
            delay=delay,
            run_mutating=include_mutating,
            include_data=True,
        )
        if out.get("skipped"):
            skipped.append(spec.route_id)
            continue
        if out.get("error") or "data" not in out:
            contract_fails.append({"route_id": spec.route_id, "error": out.get("error", "no data")})
            continue
        status = int(out["status"])
        data = _sanitize_value(out["data"])
        try:
            validate_response(spec, status, data)
        except ContractError as e:
            contract_fails.append({"route_id": spec.route_id, "error": str(e)})
            continue
        entry = {
            "route_id": spec.route_id,
            "status": status,
            "data": data,
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "live_path": out.get("path"),
        }
        by_id[spec.route_id] = entry
        recorded.append(spec.route_id)

    cassette = {
        "meta": {
            **(existing.get("meta") or {}),
            "version": 1,
            "description": "Kayıtlı API yanıtları — record_api_cassette.py ile güncellenir",
            "last_record_account": "live",
        },
        "default_context": new_context,
        "replays": [by_id[r.route_id] for r in BOT_API_ROUTES if r.route_id in by_id],
    }

    if not dry_run:
        save_cassette(cassette, path)

    replay_check = run_replay_suite(cassette)
    return {
        "ok": replay_check.get("ok") and not contract_fails,
        "recorded": recorded,
        "skipped": skipped,
        "contract_failures": contract_fails,
        "context": new_context,
        "cassette_path": str(path),
        "dry_run": dry_run,
        "replay_ok": replay_check.get("ok"),
        "replay_passed": replay_check.get("passed"),
        "replay_total": replay_check.get("total"),
    }
