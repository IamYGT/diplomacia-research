"""Dashboard readiness + catalog probe."""

from unittest.mock import MagicMock, patch

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.catalog import load_catalog, load_probe_extra
from diplomacy_bot.dashboard_readiness import enrich_snapshot_row, skills_from_profile_player
from diplomacy_bot.store import Account


def _acc():
    return Account(
        id=1,
        name="ygt",
        token="tok",
        player_id="p",
        username="t",
        autofarm=True,
        last_farm_at=0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
    )


def test_skills_from_profile():
    assert skills_from_profile_player({"skills": {"kisla": 5}})["kisla"] == 5


def test_enrich_snapshot_sets_readiness_fields():
    acc = _acc()
    row = {
        "work_wait_ms": 0,
        "pill_cooldown_ms": 0,
        "free_attack": True,
        "free_attack_cooldown_ms": 0,
        "auto_work_active": False,
        "auto_war_active": False,
        "pills": 10,
        "diamonds": 100,
        "passive_available": 2,
        "class": "kalemiye",
        "active_skills": {"kisla": 50},
    }
    with patch("diplomacy_bot.dashboard_readiness.probe_readiness_light") as mock_probe:
        mock_probe.return_value = {
            "quests": {"claimable_count": 0},
            "auto": {"work_ready": True},
            "wars": {},
            "passive": {},
            "craft": {},
            "training": {"ready": True},
        }
        out = enrich_snapshot_row(acc, dict(row))
    assert "quests_claimable" in out
    assert "training_ready" in out
    assert out.get("stat_queue_summary")


def test_probe_extra_in_catalog():
    extra = load_probe_extra()
    assert any(e.get("path") == "/init/data" for e in extra)
    paths = [e.get("path") for e in load_catalog()]
    assert "/init/data" in paths
