"""Onboarding farm tail + connect wiring testleri."""

from __future__ import annotations

from diplomacy_bot.easy_role import format_onboarding_done_tail


def test_onboarding_done_farm_no_war_button():
    tail = format_onboarding_done_tail(war_enabled=False, keyboard_hidden=False)
    assert "Savaşa Vur" not in tail
    assert "Altın Kazan" in tail
    assert "izleme" in tail


def test_onboarding_done_war_has_contrib_hint():
    tail = format_onboarding_done_tail(war_enabled=True, keyboard_hidden=False)
    assert "Savaşa Vur" in tail


def test_wire_save_account_sets_flag():
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.connect_save import wire_save_account

    prev = getattr(ta, "_save_account", None)
    prev_wired = getattr(ta, "_save_account_wired", False)
    try:
        if prev_wired:
            ta._save_account_wired = False
        wire_save_account()
        assert getattr(ta, "_save_account_wired", False) is True
        assert callable(ta._save_account)
    finally:
        if prev is not None:
            ta._save_account = prev
        ta._save_account_wired = prev_wired
