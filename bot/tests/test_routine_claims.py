"""routine_claims + coach dashboard testleri."""

from unittest.mock import patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.dashboard_coach import format_coach_dashboard, score_coach_cues
from diplomacy_bot.routine_claims import (
    infer_daily_from_quests,
    run_routine_claims,
    try_daily_claim,
)


def test_infer_daily_from_quests_rewarded():
    q = [{"quest_key": "daily_login", "rewarded": True, "progress": 1, "target": 1}]
    assert infer_daily_from_quests(q)["daily_claimed"] is True


def test_infer_daily_available_when_claimable():
    q = [{"quest_key": "daily_login", "rewarded": False, "progress": 1, "target": 1}]
    assert infer_daily_from_quests(q)["daily_available"] is True


def test_try_daily_claim_ok():
    def api(method, path, token, body=None, delay=0):
        return 200, {"claimed": True, "reward": {"money": 5000}}

    r = try_daily_claim("tok", _api=api)
    assert r["ok"] and r["claimed"]


def test_try_daily_claim_already():
    def api(method, path, token, body=None, delay=0):
        return 400, {"error": "Bugün zaten alındı"}

    r = try_daily_claim("tok", _api=api)
    assert r.get("already_claimed")


def test_run_routine_claims_respects_flags():
    cfg = AccountConfig(account_name="x", auto_daily_claim=False, auto_quest_claim=False)

    with patch("diplomacy_bot.routine_claims.try_daily_claim") as d, patch(
        "diplomacy_bot.routine_claims.try_quest_claims"
    ) as q:
        out = run_routine_claims("tok", cfg)
        d.assert_not_called()
        q.assert_not_called()
        assert out == {}


def _acc():
    from diplomacy_bot.store import Account

    return Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="YGT",
        autofarm=True,
        last_farm_at=0,
        last_balance=0,
        proxy_id="direct",
        proxy_url=None,
        status="active",
    )


def test_coach_cues_daily_priority():
    acc = _acc()
    cues = score_coach_cues(
        {"health": 80, "daily_available": True, "daily_claimed": False, "work_ready": True},
        acc,
    )
    assert cues[0].score >= 55


def test_coach_dashboard_compact():
    acc = _acc()
    html_out = format_coach_dashboard(
        acc,
        {
            "username": "YGT",
            "level": 10,
            "province": "İsfahan",
            "health": 80,
            "balance": 1000000,
            "diamonds": 2000,
            "pills": 50,
            "work_ready": True,
            "_live": True,
        },
    )
    assert "📡" in html_out
    assert "Şimdi ne yapmalı" not in html_out
