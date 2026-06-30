"""Stat kuyruk — cooldown sonrası tetik."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import stats
from diplomacy_bot.stat_queue import (
    is_wake_due,
    note_pending_wake,
    should_tick_now,
    tick_stat_queue,
)
from diplomacy_bot.store import Account


def _acc(name="ygt"):
    return Account(
        id=1,
        name=name,
        token="tok",
        player_id="p1",
        username="t",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
    )


def test_skill_not_pending_when_cooldown_elapsed():
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    at = past.strftime("%Y-%m-%dT%H:%M:%S.") + f"{past.microsecond // 1000:03d}Z"
    active = {"kisla": 53, "kisla_pending": 54, "kisla_pending_at": at}
    assert stats.skill_is_pending(active, "kisla") is False


def test_skill_not_pending_when_level_applied():
    active = {"kisla": 54, "kisla_pending": 54, "kisla_pending_at": "2020-01-01T00:00:00Z"}
    assert stats.skill_is_pending(active, "kisla") is False


def test_wake_schedules_after_upgrade():
    import diplomacy_bot.stat_queue as sq

    sq._WAKE_AT.clear()
    sq._LAST_RUN.clear()
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    at = future.strftime("%Y-%m-%dT%H:%M:%S.") + f"{future.microsecond // 1000:03d}Z"
    note_pending_wake("ygt", pending_at=at)
    assert is_wake_due("ygt") is False


def test_should_tick_when_other_skill_ready_during_pending():
    import diplomacy_bot.stat_queue as sq

    sq._WAKE_AT.clear()
    sq._LAST_RUN.clear()
    future = datetime.now(timezone.utc) + timedelta(seconds=300)
    at = future.strftime("%Y-%m-%dT%H:%M:%S.") + f"{future.microsecond // 1000:03d}Z"
    active = {
        "kisla": 53,
        "kisla_pending": 54,
        "kisla_pending_at": at,
        "savas_teknikleri": 40,
    }
    cfg = AccountConfig("ygt", stat_priority=["savas_teknikleri", "kisla"], stat_auto_enabled=True)
    note_pending_wake("ygt", pending_at=at)
    assert is_wake_due("ygt") is False
    assert should_tick_now(active, cfg, "ygt") is True


def test_tick_runs_when_wake_due():
    import diplomacy_bot.stat_queue as sq

    sq._WAKE_AT.clear()
    sq._LAST_RUN.clear()
    cfg = AccountConfig("ygt", stat_auto_enabled=True)

    def fake_auto(token, cfg, **kw):
        return {"passive": [], "upgrades": [{"ok": True, "skill": "savas_teknikleri", "pending_at": None}]}

    with patch("diplomacy_bot.stat_queue.get_config", return_value=cfg):
        with patch("diplomacy_bot.stat_queue.stats.get_active_skills", return_value={"kisla": 54}):
            with patch("diplomacy_bot.stat_queue.stats.run_stat_automation", side_effect=fake_auto):
                with patch("diplomacy_bot.stat_queue.account_context"):
                    r = tick_stat_queue(_acc())
    assert r is not None
    assert r.get("upgrades")


def test_tick_suspends_on_token_auth_error():
    """Token 401/403 → stat_queue upgrade denemeden backoff'a girer.

    Token ölü iken her dakika profile→401 çağrısı dashboard bant genişliğini
    boğuyordu. get_active_skills {} + son HTTP 401 → _TOKEN_DEAD backoff set.
    """
    import diplomacy_bot.stat_queue as sq

    sq._WAKE_AT.clear()
    sq._LAST_RUN.clear()
    sq._TOKEN_DEAD.clear()
    sq._FUNDS_BACKOFF.clear()
    stats._LAST_PROFILE_STATUS = 401
    cfg = AccountConfig("ygt", stat_auto_enabled=True)

    with patch("diplomacy_bot.stat_queue.get_config", return_value=cfg):
        with patch("diplomacy_bot.stat_queue.stats.get_active_skills", return_value={}):
            with patch("diplomacy_bot.stat_queue.account_context"):
                r = tick_stat_queue(_acc())
    assert r is None  # upgrade denemedi
    assert sq._TOKEN_DEAD.get("ygt", 0) > 0  # backoff set

    # Backoff aktifken sonraki tick erken döner (profile çağrısı yapmaz).
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        return {}

    with patch("diplomacy_bot.stat_queue.stats.get_active_skills", side_effect=boom):
        with patch("diplomacy_bot.stat_queue.account_context"):
            r2 = tick_stat_queue(_acc())
    assert r2 is None
    assert called["n"] == 0  # profile çağrılmadı (backoff erken-return)


def test_preview_queue_ready_skill():
    import diplomacy_bot.stat_queue as sq

    sq._WAKE_AT.clear()
    sq._LAST_RUN.clear()
    active = {"kisla": 52, "savas_teknikleri": 40}
    cfg = AccountConfig("ygt", stat_priority=["savas_teknikleri", "kisla"], stat_auto_enabled=True)
    preview = sq.preview_stat_queue(active, cfg, "ygt")
    assert preview["kind"] == "ready"
    assert preview["ready_now"] is True


def test_preview_queue_waiting_cooldown():
    import diplomacy_bot.stat_queue as sq

    sq._WAKE_AT.clear()
    sq._LAST_RUN.clear()
    future = datetime.now(timezone.utc) + timedelta(seconds=120)
    at = future.strftime("%Y-%m-%dT%H:%M:%S.") + f"{future.microsecond // 1000:03d}Z"
    active = {"kisla": 53, "kisla_pending": 54, "kisla_pending_at": at}
    cfg = AccountConfig("ygt", stat_priority=["kisla"], stat_auto_enabled=True)
    note_pending_wake("ygt", pending_at=at)
    preview = sq.preview_stat_queue(active, cfg, "ygt")
    assert preview["kind"] == "waiting"
    assert preview["seconds_until"] is not None
    assert preview["seconds_until"] >= 100
    assert "Kışla bitince" in preview["summary"]
    assert "sn" in preview["summary"]


def test_preview_queue_ready_while_other_pending():
    import diplomacy_bot.stat_queue as sq

    sq._WAKE_AT.clear()
    sq._LAST_RUN.clear()
    future = datetime.now(timezone.utc) + timedelta(seconds=300)
    at = future.strftime("%Y-%m-%dT%H:%M:%S.") + f"{future.microsecond // 1000:03d}Z"
    active = {
        "kisla": 53,
        "kisla_pending": 54,
        "kisla_pending_at": at,
        "savas_teknikleri": 40,
    }
    cfg = AccountConfig("ygt", stat_priority=["savas_teknikleri", "kisla"], stat_auto_enabled=True)
    preview = sq.preview_stat_queue(active, cfg, "ygt")
    assert preview["kind"] == "ready"
    assert "Savaş teknikleri hazır" in preview["summary"]
