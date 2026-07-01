"""Frontend bundle API discovery tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import discover_frontend_api as disc  # noqa: E402


def test_discover_paths_from_static_bundle(monkeypatch):
    html = '<script src="/_expo/static/js/web/index.js" defer></script>'
    bundle = (
        "const api={"
        "getStatus:e=>h('/factories/work-status',{token:e}),"
        "permit:e=>h('/employment/apply',{method:'POST',token:e}),"
        "workPermit:e=>h('/work-permits/request',{method:'POST',token:e}),"
        "move:(e,t)=>h('/factories/move',{method:'POST',token:e,body:{factory_id:t}}),"
        "attack:(e,t)=>h(`/training-wars/${t}/attack`,{method:'POST',token:e})"
        "};"
    )

    def fake_fetch(url: str, *, timeout: int = 30) -> str:
        return html if url == "https://diplomacia.com.tr/" else bundle

    monkeypatch.setattr(disc, "_fetch", fake_fetch)

    report = disc.discover_paths()
    routes = {(r["method"], r["path"]) for r in report["routes"]}
    assert ("GET", "/factories/work-status") in routes
    assert ("POST", "/employment/apply") in routes
    assert ("POST", "/work-permits/request") in routes
    assert ("POST", "/factories/move") in routes
    assert ("POST", "/training-wars/{id}/attack") in routes


def test_summarize_capability_candidates_groups_goal_routes():
    report = {
        "routes": [
            {"method": "GET", "path": "/factories/work-status", "registered": True},
            {"method": "POST", "path": "/training-wars/{id}/attack", "registered": True},
            {"method": "GET", "path": "/players/profile", "registered": True},
        ]
    }

    summary = {item["label"]: item for item in disc.summarize_capability_candidates(report)}

    assert summary["work"]["count"] == 1
    assert summary["training"]["count"] == 1


def test_keyword_contexts_surface_non_route_mentions(monkeypatch):
    html = '<script src="/_expo/static/js/web/index.js" defer></script>'
    bundle = "const permitPanel='Work permit unavailable';function createTrainingWar(){return null}"

    def fake_fetch(url: str, *, timeout: int = 30) -> str:
        return html if url == "https://diplomacia.com.tr/" else bundle

    monkeypatch.setattr(disc, "_fetch", fake_fetch)

    rows = disc.discover_keyword_contexts(keywords=("permit", "create"), limit_per_keyword=2)

    assert {r["keyword"] for r in rows} == {"permit", "create"}
    assert any("permitPanel" in r["snippet"] for r in rows)
    assert any("createTrainingWar" in r["snippet"] for r in rows)
