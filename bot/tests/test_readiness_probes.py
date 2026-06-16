"""readiness_probes + dashboard_markup tests."""

import time
from unittest.mock import patch

from diplomacy_bot.dashboard_markup import dashboard_inline_markup
from diplomacy_bot.dashboard_readiness import enrich_snapshot_row, invalidate_readiness_cache
from diplomacy_bot.readiness_probes import build_readiness_from_probes, readiness_fields
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


def test_readiness_cache_skips_second_probe():
    invalidate_readiness_cache()
    acc = _acc()
    row = {
        "work_wait_ms": 0,
        "pill_cooldown_ms": 0,
        "free_attack": True,
        "pills": 10,
        "diamonds": 100,
        "passive_available": 0,
        "class": "x",
        "active_skills": {},
    }
    calls = {"n": 0}

    def fake_light(token, name, r, **kw):
        calls["n"] += 1
        return {
            "quests": {"claimable_count": 2},
            "auto": {"work_ready": True},
            "wars": {},
            "passive": {},
            "craft": {},
            "training": {"ready": True},
        }

    with patch("diplomacy_bot.dashboard_readiness.probe_readiness_light", side_effect=fake_light):
        enrich_snapshot_row(acc, row)
        out = enrich_snapshot_row(acc, row)
    assert calls["n"] == 1
    assert out.get("quests_claimable") == 2


def test_dashboard_markup_quest_badge():
    acc = _acc()
    mk = dashboard_inline_markup(
        acc,
        {"health": 100, "quests_claimable": 3, "training_ready": True},
    )
    flat = [b.text for row in mk.inline_keyboard for b in row]
    assert any("Görev (3)" in t for t in flat)
    assert any("Antrenman" in t for t in flat)
    assert any("📜3" in t for t in flat)


def test_build_readiness_from_probes():
    r = build_readiness_from_probes(
        {"quests": {"claimable_count": 1}, "auto": {"work_ready": True}, "training": {"ready": True}}
    )
    fields = readiness_fields(r)
    assert fields["quests_claimable"] == 1
    assert fields["training_ready"] is True
