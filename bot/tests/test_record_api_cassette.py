"""record_cassette_from_live + sanitize testleri."""

from __future__ import annotations

from diplomacy_bot.api_route_registry import BOT_API_ROUTES
from diplomacy_bot.api_route_replay import _sanitize_value, record_cassette_from_live


def test_sanitize_redacts_jwt():
    out = _sanitize_value({"token": "eyJ" + "x" * 80, "ok": True})
    assert out["token"] == "<redacted>"
    assert out["ok"] is True


def test_record_cassette_merges_safe_only():
    def fake_api(method, path, token, body=None, delay=0):
        if path == "/players/profile":
            return 200, {"player": {"username": "live"}, "username": "live"}
        if path == "/players/passive-skills":
            return 200, {"passive_skills": {}, "available_points": 0}
        if path == "/auto/status":
            return 200, {"next_work_in_ms": 0, "health_pills": 5}
        if path == "/countries":
            return 200, {"countries": []}
        if path == "/quests":
            return 200, {"quests": []}
        if path == "/wars/my-country":
            return 200, {"wars": [{"id": "w-live"}]}
        if path == "/wars":
            return 200, {"wars": []}
        if path == "/training-wars/my":
            return 404, {"error": "not found"}
        if path == "/factories/my":
            return 200, {"factories": []}
        if path.startswith("/factories/region"):
            return 200, {"factories": []}
        if path == "/factories/work-status":
            return 200, {"working": False}
        if path == "/provinces/travel/status":
            return 200, {"traveling": False}
        if path == "/provinces/all":
            return 200, {"provinces": []}
        if path == "/military/me":
            return 200, {"military_power": 0}
        if path == "/military-ops/my":
            return 404, {"error": "not found"}
        if path == "/online":
            return 200, {"online": 1}
        if path == "/online/players":
            return 200, {"players": []}
        if path == "/players/ping":
            return 200, {"ok": True}
        return 404, {"error": "miss"}

    report = record_cassette_from_live(
        fake_api,
        "tok",
        include_mutating=False,
        dry_run=True,
    )
    assert "players.profile" in report["recorded"]
    assert "factories.work" not in report["recorded"]
    assert report["context"].get("war_id") == "w-live"
    assert report.get("replay_ok")


def test_record_cassette_replay_still_passes_after_dry_run():
    def fake_api(method, path, token, body=None, delay=0):
        if path == "/players/profile":
            return 200, {"player": {"username": "x"}}
        return 200, {}

    report = record_cassette_from_live(fake_api, "tok", dry_run=True)
    assert report.get("replay_total") == len(BOT_API_ROUTES)
