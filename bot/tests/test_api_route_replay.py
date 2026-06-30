"""API replay cassette — mutating route'lar CI'da kayıtlı yanıtla doğrulanır."""

from __future__ import annotations

import pytest

from diplomacy_bot.api_route_registry import BOT_API_ROUTES, mutating_routes
from diplomacy_bot.api_route_replay import (
    compare_catalog_vs_registry,
    load_cassette,
    replay_index,
    routes_missing_replay,
    run_replay_suite,
    validate_cassette_contracts,
)


def test_every_route_has_replay_cassette():
    cassette = load_cassette()
    missing = routes_missing_replay(cassette)
    assert not missing, f"api_replay.json eksik route_id: {missing}"


def test_replay_cassette_contracts_valid():
    cassette = load_cassette()
    failures = validate_cassette_contracts(cassette)
    assert not failures, failures


def test_replay_suite_all_routes_pass():
    report = run_replay_suite()
    assert report["ok"], (
        f"missing={report.get('missing_replay')} "
        f"contract={report.get('contract_failures')} "
        f"failures={report.get('failures')[:3]}"
    )
    assert report["passed"] == len(BOT_API_ROUTES)


def test_mutating_routes_covered_by_replay():
    cassette = load_cassette()
    idx = replay_index(cassette)
    missing = [r.route_id for r in mutating_routes() if r.route_id not in idx]
    assert not missing, f"mutating replay eksik: {missing}"


def test_catalog_covers_bot_registry():
    diff = compare_catalog_vs_registry()
    if diff.get("skipped"):
        pytest.skip(diff.get("reason", "katalog yok"))
    assert diff["ok"], f"catalog'da eksik bot yolları: {diff.get('missing_in_catalog')}"


@pytest.mark.parametrize("route_id", [r.route_id for r in mutating_routes()])
def test_mutating_route_replay_entry(route_id: str):
    cassette = load_cassette()
    idx = replay_index(cassette)
    assert route_id in idx, f"{route_id} için replay yok"
