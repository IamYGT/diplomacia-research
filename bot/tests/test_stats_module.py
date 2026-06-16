"""modules/stats — upgrade + spend."""

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import stats


def test_normalize_upgrade_type():
    assert stats.normalize_upgrade_type("gold") == "money"
    assert stats.normalize_upgrade_type("altin") == "money"
    assert stats.normalize_upgrade_type("diamond") == "diamond"
    assert stats.normalize_upgrade_type("elmas") == "diamond"


def test_upgrade_skill_sends_money_type():
    calls = []

    def fake_api(method, path, token, body=None, delay=0):
        calls.append((method, path, body))
        return 200, {
            "success": True,
            "skill": "kisla",
            "target_level": 53,
            "cost": 5000,
            "cost_type": "money",
            "pending_at": "2026-06-14T00:00:00Z",
            "cooldown_ms": 27000,
        }

    r = stats.upgrade_skill("tok", "kisla", "gold", _api=fake_api)
    assert r["ok"] is True
    assert r["new_level"] == 53
    assert calls[0][2] == {"skill": "kisla", "type": "money"}
    assert r["api_type"] == "money"


def test_upgrade_skill_diamond_type():
    def fake_api(method, path, token, body=None, delay=0):
        return 200, {"success": True, "target_level": 15, "cost_type": "diamond"}

    r = stats.upgrade_skill("tok", "bilim_insani", "diamonds", _api=fake_api)
    assert r["ok"] is True
    assert r["currency"] == "diamond"


def test_upgrade_skill_insufficient_balance():
    def fake_api(method, path, token, body=None, delay=0):
        return 200, {
            "error": "insufficientBalance",
            "required": 12500,
            "cost_type": "money",
        }

    r = stats.upgrade_skill("tok", "kisla", "gold", _api=fake_api)
    assert r["ok"] is False
    assert r["required"] == 12500
    assert "Yetersiz bakiye" in r["error"]
    assert "12.500" in r["error"]


def test_upgrade_skill_insufficient_diamond():
    def fake_api(method, path, token, body=None, delay=0):
        return 200, {"error": "insufficientDiamond", "required": 50}

    r = stats.upgrade_skill("tok", "bilim_insani", "diamond", _api=fake_api)
    assert r["ok"] is False
    assert "Yetersiz elmas" in r["error"]
    assert "50" in r["error"]


def test_pending_seconds_remaining_future():
    from datetime import datetime, timedelta, timezone

    end = datetime.now(timezone.utc) + timedelta(seconds=24)
    at = end.strftime("%Y-%m-%dT%H:%M:%S.") + f"{end.microsecond // 1000:03d}Z"
    active = {"bilim_insani_pending_at": at}
    sec = stats.pending_seconds_remaining(active, "bilim_insani")
    assert sec is not None
    assert 20 <= sec <= 30


def test_format_upgrade_error():
    assert "12.500" in stats.format_upgrade_error({"required": 12500}, "money")
    assert "💎" in stats.format_upgrade_error({"required": 50}, "diamond")


def test_pending_seconds_remaining_ms_field():
    active = {"kisla_cooldown_ms": 24_000}
    sec = stats.pending_seconds_remaining(active, "kisla")
    assert sec == 24


def test_skill_is_pending():
    active = {"kisla": 52, "bilim_insani_pending": 19, "bilim_insani_pending_at": "x"}
    assert stats.skill_is_pending(active, "bilim_insani") is True
    assert stats.skill_is_pending(active, "kisla") is False


def test_resolve_active_priority():
    cfg = AccountConfig("x", stat_priority=["bilim_insani", "kisla"])
    ordered = stats.resolve_active_priority(cfg, ["kisla", "savas_teknikleri", "bilim_insani"])
    assert ordered[0] == "bilim_insani"


def test_spend_passive():
    def fake_api(method, path, token, body=None, delay=0):
        return 200, {"new_level": 4}

    r = stats.spend_passive("tok", "ekonomi", 3, _api=fake_api)
    assert r["ok"] is True
