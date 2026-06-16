"""Farm merkezi testleri."""

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.farm_board import (
    analyze_farm_board_enriched,
    format_farm_board_html,
    farm_board_callback_rows,
)


def _pack():
    return {
        "profile": type("P", (), {"diamonds": 5000, "health_pills": 3, "balance": 100000, "health": 80, "username": "ygt"})(),
        "auto": {
            "next_work_in_ms": 489000,
            "pill_cooldown_ms": 0,
            "health": 80,
            "health_pills": 3,
            "health_max": 100,
        },
        "work": {"working": False},
    }


def test_analyze_farm_board_cooldown():
    a = analyze_farm_board_enriched(_pack(), AccountConfig("t"))
    assert a["work_ms"] > 0
    assert a["next_action"] == "wait_work"
    assert a["diamonds_per_work"] == 20


def test_format_farm_board():
    pack = _pack()
    html_out = format_farm_board_html(pack, analyze_farm_board_enriched(pack, AccountConfig("x")))
    assert "Farm merkezi" in html_out
    assert "Elmas" in html_out or "elmas" in html_out
    assert "8" in html_out or "dk" in html_out


def test_farm_callbacks_craft_buttons():
    a = analyze_farm_board_enriched(_pack(), AccountConfig("x", craft_diamond_batch=3000))
    rows = farm_board_callback_rows(a)
    flat = [cb for row in rows for _, cb in row]
    assert any(cb.startswith("farm:craft:") for cb in flat)
