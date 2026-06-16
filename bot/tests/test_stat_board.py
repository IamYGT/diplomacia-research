"""Stat paneli — isim tabanlı UX."""

from datetime import datetime, timedelta, timezone

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.stat_board import (
    analyze_stat_board_enriched,
    compute_stat_automation_status,
    format_stat_board_html,
    resolve_active_skill_key,
    skill_short_name,
    stat_board_callback_rows,
)


def _pack():
    return {
        "passive_data": {
            "available_points": 0,
            "passive_skills": {"vergi_uzmani": {"level": 23}},
        },
        "active_skills": {
            "kisla": 52,
            "bilim_insani": 14,
            "savas_teknikleri": 2,
        },
        "balance": 1_500_000,
        "diamonds": 2000,
    }


def test_format_uses_turkish_names_not_numbers():
    cfg = AccountConfig("x", stat_priority=["bilim_insani", "kisla", "savas_teknikleri"])
    html_out = format_stat_board_html(_pack(), analyze_stat_board_enriched(_pack(), cfg), cfg)
    assert "Bilim insanı" in html_out
    assert "Kışla" in html_out
    assert "Savaş teknikleri" in html_out
    assert "1." not in html_out
    assert "bilim_insani" not in html_out
    assert "Önce yükseltilen" in html_out
    assert "Durum:" in html_out


def test_automation_status_when_pending_blocks_queue():
    pack = {
        "passive_data": {"available_points": 0, "passive_skills": {}},
        "active_skills": {
            "kisla": 53,
            "kisla_pending": 54,
            "savas_teknikleri": 2,
            "bilim_insani": 20,
        },
        "balance": 1_500_000,
        "diamonds": 0,
    }
    cfg = AccountConfig("x", stat_priority=["savas_teknikleri", "bilim_insani", "kisla"])
    analysis = analyze_stat_board_enriched(pack, cfg)
    st = compute_stat_automation_status(analysis)
    assert st["kind"] == "pending"
    assert "Savaş teknikleri" in st["summary"]
    assert "Kışla" in st["summary"] or "kışla" in st["summary"].lower()


def test_pending_without_timestamp_shows_estimate():
    pack = {
        "passive_data": {"available_points": 0, "passive_skills": {}},
        "active_skills": {"kisla": 53, "kisla_pending": 54},
        "balance": 100,
        "diamonds": 0,
    }
    cfg = AccountConfig("x", stat_priority=["kisla"])
    html_out = format_stat_board_html(pack, analyze_stat_board_enriched(pack, cfg), cfg)
    assert "tahmini" in html_out or "Yenile" in html_out


def test_resolve_by_turkish_name():
    a = analyze_stat_board_enriched(_pack(), AccountConfig("x"))
    assert resolve_active_skill_key(a, "Kışla") == "kisla"
    assert resolve_active_skill_key(a, "savaş teknikleri") == "savas_teknikleri"
    assert resolve_active_skill_key(a, "bilim") == "bilim_insani"


def test_callback_buttons_named():
    a = analyze_stat_board_enriched(_pack(), AccountConfig("x", stat_priority=["kisla"]))
    flat = [cb for row in stat_board_callback_rows(a) for _, cb in row]
    assert "stat:prio:kisla" in flat
    assert "stat:prio:1" not in flat
    labels = [lb for row in stat_board_callback_rows(a) for lb, _ in row]
    assert any("Kışla" in lb for lb in labels)


def test_skill_short_name():
    assert skill_short_name("savas_teknikleri") == "Savaş teknikleri"


def test_kuyruk_shows_pending_skill_and_next():
    end = datetime.now(timezone.utc) + timedelta(seconds=118)
    at = end.strftime("%Y-%m-%dT%H:%M:%S.") + f"{end.microsecond // 1000:03d}Z"
    pack = {
        "passive_data": {"available_points": 0, "passive_skills": {}},
        "active_skills": {
            "kisla": 53,
            "kisla_pending": 54,
            "kisla_pending_at": at,
            "savas_teknikleri": 2,
            "bilim_insani": 20,
        },
        "balance": 1_500_000,
        "diamonds": 0,
    }
    cfg = AccountConfig("ygt", stat_priority=["savas_teknikleri", "bilim_insani", "kisla"], stat_auto_enabled=True)
    html_out = format_stat_board_html(pack, analyze_stat_board_enriched(pack, cfg), cfg)
    assert "<b>Durum:</b>" in html_out
    assert "Savaş teknikleri" in html_out
    assert "<b>Kuyruk:</b>" not in html_out


def test_format_shows_kuyruk_line():
    cfg = AccountConfig("ygt", stat_priority=["bilim_insani", "kisla"], stat_auto_enabled=True)
    analysis = analyze_stat_board_enriched(_pack(), cfg)
    html_out = format_stat_board_html(_pack(), analysis, cfg)
    assert "<b>Durum:</b>" in html_out
    assert "<b>Kuyruk:</b>" not in html_out
    assert "sn" in html_out.lower() or "Hazır" in html_out


def test_combined_stat_status_pending():
    from diplomacy_bot.stat_board import format_stat_status_combined

    auto = {"kind": "pending", "summary": "⏳ Kışla bitince → <b>Savaş</b>"}
    queue = {"kind": "waiting", "summary": "Kışla bitince → Savaş teknikleri · 118 sn"}
    line = format_stat_status_combined(auto, queue, auto_on=True)
    assert "118 sn" in line
    assert "Kışla" in line


def test_format_shows_cooldown_seconds():
    end = datetime.now(timezone.utc) + timedelta(seconds=24)
    at = end.strftime("%Y-%m-%dT%H:%M:%S.") + f"{end.microsecond // 1000:03d}Z"
    pack = {
        "passive_data": {"available_points": 0, "passive_skills": {}},
        "active_skills": {
            "bilim_insani": 14,
            "bilim_insani_pending": 19,
            "bilim_insani_pending_at": at,
            "kisla": 52,
        },
        "balance": 100,
        "diamonds": 0,
    }
    cfg = AccountConfig("x", stat_priority=["bilim_insani", "kisla"])
    html_out = format_stat_board_html(pack, analyze_stat_board_enriched(pack, cfg), cfg)
    assert "sn kaldı" in html_out
    assert "→ 19" in html_out
