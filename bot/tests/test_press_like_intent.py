"""Makale beğen intent — ASCII alias ve otomatik beğen."""

from __future__ import annotations

from unittest.mock import patch

from diplomacy_bot.press_like_intent import try_press_like_fast_path


class _Acc:
    name = "ygt"
    token = "tok"


def test_makale_begen_ascii_alias():
    with patch("diplomacy_bot.press_likes.auto_like_articles", return_value={"liked": 1, "skipped": 0, "errors": 0, "samples": []}):
        r = try_press_like_fast_path("makale begen", _Acc())
    assert r is not None and "beğenildi" in r.reply


def test_otomatik_begen_standalone():
    with patch("diplomacy_bot.press_likes.auto_like_articles", return_value={"liked": 0, "skipped": 2, "errors": 0, "samples": []}):
        r = try_press_like_fast_path("otomatik beğen", _Acc())
    assert r is not None and "oylanmış" in r.reply


def test_makale_begen_ac_confirmation():
    with patch("diplomacy_bot.account_config.update_config_field") as upd:
        r = try_press_like_fast_path("makale beğen aç", _Acc())
    assert r is not None and "açıldı" in r.reply
    upd.assert_called_once_with("ygt", auto_like_articles=True)
    assert "kapat" in r.reply.lower()


def test_hook_installed_on_work_mode_hooks():
    from diplomacy_bot import intent_router as ir
    from diplomacy_bot.work_mode_hooks import install_work_mode_hooks

    ir._press_like_intent_installed = False
    install_work_mode_hooks()
    assert getattr(ir, "_press_like_intent_installed", False) is True
    with patch("diplomacy_bot.press_likes.auto_like_articles", return_value={"liked": 0, "skipped": 0, "errors": 0, "samples": []}):
        r = ir.try_fast_path("makale begen", "ygt")
    assert r is not None and "makale" in r.reply.lower()


def test_legacy_help_includes_press_commands():
    from diplomacy_bot import telegram_ui as ui
    from diplomacy_bot.press_like_intent import install_press_like_ui_hooks

    if not hasattr(ui, "_format_help_html_legacy"):
        ui._format_help_html_legacy = lambda: "<b>Komutlar</b> /help"
    ui._press_like_ui_installed = False
    install_press_like_ui_hooks()
    body = ui._format_help_html_legacy()
    assert "makale beğen" in body


def test_dashboard_footer_when_auto_like_off():
    from diplomacy_bot.press_like_intent import press_like_dashboard_footer

    with patch("diplomacy_bot.account_config.get_config") as gc:
        gc.return_value.auto_like_articles = False
        foot = press_like_dashboard_footer(_Acc())
    assert "makale beğen aç" in foot


def test_dashboard_footer_active_badge_when_auto_like_on():
    from diplomacy_bot.press_like_intent import press_like_dashboard_footer

    with patch("diplomacy_bot.account_config.get_config") as gc:
        gc.return_value.auto_like_articles = True
        foot = press_like_dashboard_footer(_Acc())
    assert "aktif" in foot.lower()
