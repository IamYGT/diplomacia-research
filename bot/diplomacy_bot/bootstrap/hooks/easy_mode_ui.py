"""Kolay mod UI — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_easy_mode_ui() -> None:
    from diplomacy_bot import telegram_ui as ui
    from diplomacy_bot.easy_mode import (
        EASY_MENU_LABELS,
        dashboard_headline,
        format_welcome_easy_html,
        main_reply_keyboard_easy,
        simplify_dashboard_html,
    )
    from diplomacy_bot.easy_role import war_ui_enabled
    from diplomacy_bot.help_easy import format_help_easy_html

    if getattr(ui, "_easy_mode_installed", False):
        return

    ui.MENU_LABELS.update(EASY_MENU_LABELS)
    _orig_norm = ui.normalize_menu_text

    def normalize_menu_text_patched(text: str) -> str | None:
        key = text.strip().lower()
        hit = EASY_MENU_LABELS.get(key)
        if hit:
            return hit
        return _orig_norm(text)

    ui.normalize_menu_text = normalize_menu_text_patched
    ui.main_reply_keyboard = main_reply_keyboard_easy  # type: ignore[assignment]

    _orig_help = ui.format_help_html
    ui.format_help_html = format_help_easy_html  # type: ignore[assignment]
    ui._format_help_html_legacy = _orig_help

    _orig_welcome = ui.format_welcome_html

    def format_welcome_patched(uid, account_name, *, gemini_ok, linked):
        return format_welcome_easy_html(uid, account_name, gemini_ok=gemini_ok, linked=linked)

    ui.format_welcome_html = format_welcome_patched  # type: ignore[assignment]

    _orig_dash = ui.format_dashboard_html

    def format_dashboard_easy(acc, snap=None):
        from diplomacy_bot.dynamic_context import snapshot_account

        snap = snap or snapshot_account(acc)
        body = _orig_dash(acc, snap)
        headline = dashboard_headline(
            snap,
            autofarm=bool(snap.get("autofarm") or acc.autofarm),
            war_enabled=war_ui_enabled(acc.name),
        )
        return f"{headline}\n\n{simplify_dashboard_html(body)}"

    ui.format_dashboard_html = format_dashboard_easy  # type: ignore[assignment]
    ui._easy_mode_installed = True
    log.info("Kolay mod UI (explicit bootstrap) kuruldu")
