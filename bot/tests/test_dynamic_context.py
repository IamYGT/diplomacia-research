"""Dashboard snapshot — hızlı okuma yolu."""

from diplomacy_bot.dynamic_context import _snapshot_live
from diplomacy_bot.store import Account


def test_snapshot_live_skips_network_enrich_when_disabled(monkeypatch):
    calls: list[str] = []

    def fake_api(method, path, token, body=None, delay=6.0):
        calls.append(path)
        if path == "/players/profile":
            return 200, {
                "player": {
                    "username": "t",
                    "level": 10,
                    "balance": 100,
                    "diamonds": 5,
                    "health": 100,
                    "health_pills": 10,
                }
            }
        if path == "/auto/status":
            return 200, {"next_work_in_ms": 0, "pill_cooldown_ms": 0}
        if path == "/players/passive-skills":
            return 200, {"available_points": 0, "passive_skills": {}}
        return 404, {}

    enrich_network = []

    def fake_enrich(acc, row, **kw):
        enrich_network.append(kw.get("network", True))
        return row

    monkeypatch.setattr("diplomacy_bot.game_api.api", fake_api)
    monkeypatch.setattr(
        "diplomacy_bot.dashboard_readiness.enrich_snapshot_row",
        fake_enrich,
    )

    acc = Account(
        id=1,
        name="x",
        token="tok",
        player_id="p1",
        username="t",
        autofarm=False,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )
    row = _snapshot_live(acc, enrich=False)
    assert row.get("username") == "t"
    assert len(calls) == 3
    assert enrich_network == [False]


def test_snapshot_live_uses_direct_api_not_slow_pool(monkeypatch):
    calls: list[float] = []

    def fake_api(method, path, token, body=None, delay=6.0):
        calls.append(float(delay))
        if path == "/players/profile":
            return 200, {
                "player": {
                    "username": "t",
                    "level": 10,
                    "balance": 100,
                    "diamonds": 5,
                    "health": 100,
                    "health_pills": 10,
                }
            }
        if path == "/auto/status":
            return 200, {"next_work_in_ms": 0, "pill_cooldown_ms": 0}
        if path == "/players/passive-skills":
            return 200, {"available_points": 0, "passive_skills": {}}
        return 404, {}

    monkeypatch.setattr("diplomacy_bot.game_api.api", fake_api)
    monkeypatch.setattr(
        "diplomacy_bot.dashboard_readiness.enrich_snapshot_row",
        lambda acc, row, **kw: row,
    )

    acc = Account(
        id=1,
        name="x",
        token="tok",
        player_id="p1",
        username="t",
        autofarm=False,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )
    row = _snapshot_live(acc)
    assert row.get("username") == "t"
    assert len(calls) == 3
    assert all(d < 1.0 for d in calls), f"snapshot should use low delay, got {calls}"
