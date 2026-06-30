"""API route registry — kod kapsamı + sözleşme fixture testleri."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from diplomacy_bot.api_route_contract import validate_response
from diplomacy_bot.api_route_probe import build_probe_context, probe_route, resolve_path
from diplomacy_bot.api_route_registry import (
    BOT_API_ROUTES,
    find_unregistered_routes,
    registry_keys,
    safe_probe_routes,
    scan_codebase_routes,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "api_contracts.json"


def test_no_unregistered_code_paths():
    """Kodda kullanılan her yol registry'de olmalı — yeni api() çağrısı CI'da yakalanır."""
    missing = find_unregistered_routes()
    assert not missing, (
        "Registry dışı API yolları (api_route_registry.py'ye ekle):\n"
        + "\n".join(f"  {m} {p}" for m, p in missing)
    )


def test_registry_has_safe_routes_for_dashboard_modules():
    """Dashboard/orchestrator modüllerinin GET yolları safe_probe."""
    required_safe = {
        ("GET", "/players/profile"),
        ("GET", "/auto/status"),
        ("GET", "/players/passive-skills"),
        ("GET", "/wars/my-country"),
        ("GET", "/training-wars/my"),
        ("GET", "/factories/work-status"),
        ("GET", "/factories/my"),
        ("GET", "/factories/world"),
        ("GET", "/provinces/travel/status"),
    }
    safe_keys = {(r.method, r.path) for r in safe_probe_routes()}
    missing = required_safe - safe_keys
    assert not missing, f"safe_probe eksik: {missing}"


def test_every_route_has_unique_id():
    ids = [r.route_id for r in BOT_API_ROUTES]
    assert len(ids) == len(set(ids)), "duplicate route_id"


@pytest.mark.parametrize("spec", BOT_API_ROUTES, ids=lambda s: s.route_id)
def test_minimal_contract_accepts_synthetic_success(spec):
    """Her route için sentetik başarı yanıtı sözleşmeyi geçmeli."""
    data: dict = {}
    if spec.any_keys:
        data[spec.any_keys[0]] = [] if spec.any_keys[0].endswith("s") else {}
    for k in spec.all_keys:
        data[k] = 0
    if not spec.any_keys and not spec.all_keys:
        data["ok"] = True
    validate_response(spec, 200, data)


@pytest.mark.parametrize("spec", BOT_API_ROUTES, ids=lambda s: s.route_id)
def test_route_path_normalized(spec):
    assert spec.path.startswith("/")
    assert " " not in spec.path


def test_contract_fixtures_match_registry():
    if not FIXTURES.exists():
        pytest.skip("fixtures/api_contracts.json yok")
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    by_id = {r.route_id: r for r in BOT_API_ROUTES}
    for entry in data.get("samples", []):
        rid = entry["route_id"]
        assert rid in by_id, f"fixture route_id bilinmiyor: {rid}"
        validate_response(by_id[rid], entry["status"], entry["data"])


def test_probe_route_skips_mutating_by_default():
    spec = next(r for r in BOT_API_ROUTES if r.route_id == "factories.work")
    out = probe_route(spec, lambda *a, **k: (200, {}), "tok", {}, run_mutating=False)
    assert out.get("skipped") and out.get("reason") == "mutating"


def test_probe_route_validates_success():
    spec = next(r for r in BOT_API_ROUTES if r.route_id == "players.profile")

    def fake_api(method, path, token, body=None, delay=0):
        return 200, {"username": "test", "level": 1, "balance": 0}

    out = probe_route(spec, fake_api, "tok", {}, run_mutating=False)
    assert out["ok"] is True
    assert out["contract"] == "pass"


def test_probe_route_fails_bad_shape():
    spec = next(r for r in BOT_API_ROUTES if r.route_id == "countries.list")

    def fake_api(method, path, token, body=None, delay=0):
        return 200, {"unexpected": True}

    out = probe_route(spec, fake_api, "tok", {}, run_mutating=False)
    assert out["ok"] is False
    assert out["contract"] == "fail"


def test_build_probe_context_extracts_war_id():
    calls = []

    def fake_api(method, path, token, body=None, delay=0):
        calls.append((method, path))
        if path == "/wars/my-country":
            return 200, {"wars": [{"id": "w99"}]}
        if path == "/players/profile":
            return 200, {"username": "x"}
        return 404, {}

    ctx = build_probe_context(fake_api, "tok", delay=0)
    assert ctx.get("war_id") == "w99"


def test_resolve_path_war_contribute():
    spec = next(r for r in BOT_API_ROUTES if r.route_id == "wars.contribute")
    p = resolve_path(spec, {"war_id": "42"})
    assert p == "/wars/42/contribute"


def test_validate_optional_404():
    spec = next(r for r in BOT_API_ROUTES if r.route_id == "training.my")
    validate_response(spec, 404, {"error": "not found"})


def test_scan_finds_profile_in_game_api():
    scanned = scan_codebase_routes()
    assert ("GET", "/players/profile") in scanned


def test_registry_covers_scan_core_paths():
    """Tarama çıktısının çoğu registry'de."""
    scanned = scan_codebase_routes()
    reg = registry_keys()
    covered = sum(1 for m, p in scanned if (m, p) in reg or ("POST", p) in reg or ("GET", p) in reg)
    ratio = covered / max(len(scanned), 1)
    assert ratio >= 0.85, f"registry kapsamı düşük: {ratio:.0%} ({covered}/{len(scanned)})"
