"""Farm merkezi testleri."""

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.farm_board import (
    _pill_status_alert,
    _show_farm_roi,
    _work_status_line,
    analyze_farm_board_enriched,
    farm_board_callback_rows,
    farm_board_inline_markup,
    format_farm_board_html,
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


def test_analyze_farm_board_prefers_profile_health_over_auto():
    pack = {
        "profile": type(
            "P",
            (),
            {"diamonds": 5000, "health_pills": 100, "balance": 100000, "health": 0, "username": "ygt"},
        )(),
        "auto": {
            "next_work_in_ms": 0,
            "pill_cooldown_ms": 0,
            "health": 100,
            "health_pills": 100,
            "health_max": 100,
        },
        "work": {"working": False},
    }
    a = analyze_farm_board_enriched(pack, AccountConfig("t"))
    assert a["health"] == 0
    assert a["next_action"] == "use_pill"
    assert a["can_work"] is False


def test_analyze_farm_board_cooldown():
    a = analyze_farm_board_enriched(_pack(), AccountConfig("t"))
    assert a["work_ms"] > 0
    assert a["next_action"] == "wait_work"
    assert a["diamonds_per_work"] == 20


def test_farm_roi_hidden_when_working_and_low_health():
    assert _show_farm_roi({"health": 0, "working": True}) is False
    assert _show_farm_roi({"health": 100, "working": True}) is True


def test_format_farm_hides_roi_when_can_zero_working():
    pack = {
        "profile": type("P", (), {"diamonds": 5000, "health_pills": 100, "balance": 100000, "health": 0, "username": "ygt"})(),
        "auto": {"next_work_in_ms": 0, "pill_cooldown_ms": 0, "health": 0, "health_pills": 100},
        "work": {"working": True, "factory_id": "fab-1"},
    }
    html_out = format_farm_board_html(pack, analyze_farm_board_enriched(pack, AccountConfig("t")))
    assert "kazanç tahmini gizlendi" in html_out
    assert "Başabaş" not in html_out


def test_work_status_line_working_with_zero_health():
    line = _work_status_line({"working": True, "work_factory_id": "fab-1", "health": 0})
    assert "Sunucu fabrikada" in line
    assert "Can 0/100" in line
    assert "Fabrikada çalışıyor" not in line


def test_farm_board_pill_cooldown_alert():
    pack = {
        "profile": type(
            "P",
            (),
            {"diamonds": 5000, "health_pills": 100, "balance": 100000, "health": 0, "username": "ygt"},
        )(),
        "auto": {
            "next_work_in_ms": 0,
            "pill_cooldown_ms": 300000,
            "health": 0,
            "health_pills": 100,
            "health_max": 100,
        },
        "work": {"working": False},
    }
    a = analyze_farm_board_enriched(pack, AccountConfig("t"))
    assert a["next_action"] == "wait_pill"
    html_out = format_farm_board_html(pack, a)
    assert "farm durdu" in html_out
    assert "Hap bekleme" in html_out
    assert _pill_status_alert(a)


def test_farm_board_pill_button_shows_cooldown():
    a = {
        "health": 0,
        "pill_ms": 300000,
        "pills": 100,
        "pill_ready": False,
        "can_use_pill": False,
        "can_work": False,
        "work_ms": 0,
        "craft_presets": [1000],
        "craft_pills_when_low": False,
        "craft_batch_cfg": 3000,
    }
    mk = farm_board_inline_markup(a)
    labels = [b.text for row in mk.inline_keyboard for b in row]
    assert any("Hap" in lb and "⏳" in lb for lb in labels)


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
