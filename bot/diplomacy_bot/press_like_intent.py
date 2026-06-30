"""Gazete makale beğenme — intent_router'a dokunmadan fast-path."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_agent import AgentResult

_PRESS_LIKE_PATTERNS = [
    r"makale\s*be[gğ]en",
    r"be[gğ]en\s*a[cç]",
    r"be[gğ]en\s*kapat",
    r"otomatik\s*be[gğ]en",
    r"makale.*be[gğ]en.*a[cç]",
    r"makale.*be[gğ]en.*kapat",
]


def _match(text: str, patterns: list[str]) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t) for p in patterns)


def try_press_like_fast_path(text: str, acc) -> "AgentResult | None":
    """Anlık beğenme veya otomatik mod aç/kapat (ğ ve ASCII begen)."""
    if not _match(text, _PRESS_LIKE_PATTERNS):
        return None

    from .ai_agent import AgentResult
    from .account_config import update_config_field
    from .press_likes import auto_like_articles, format_like_result_html

    turn_on = _match(text, [r"a[cç]|açık|acik|başlat|baslat|aktif"])
    turn_off = _match(text, [r"kapat|kapa|durdur|pasif"])
    if turn_on:
        update_config_field(acc.name, auto_like_articles=True)
        return AgentResult(
            reply=(
                "📰✅ Makale otomatik beğenme <b>açıldı</b>\n"
                "Yeni makaleler ~5 dk'da bir beğenilir.\n"
                "<i>Kapatmak için: <code>makale beğen kapat</code></i>"
            ),
            parse_mode="HTML",
        )
    if turn_off:
        update_config_field(acc.name, auto_like_articles=False)
        return AgentResult(
            reply="📰⚪ Makale otomatik beğenme <b>kapatıldı</b>.",
            parse_mode="HTML",
        )
    res = auto_like_articles(acc.token, acc.name)
    return AgentResult(reply=format_like_result_html(res), parse_mode="HTML")


def install_press_like_intent_hook() -> None:
    """try_fast_path önüne makale beğen handler'ı ekle."""
    import logging

    from . import intent_router as ir

    log = logging.getLogger(__name__)
    if getattr(ir, "_press_like_intent_installed", False):
        return

    _orig = ir.try_fast_path

    def try_fast_path_patched(user_message: str, default_account: str):
        from .store import get_account

        acc = get_account(default_account)
        if acc:
            hit = try_press_like_fast_path(user_message, acc)
            if hit is not None:
                return hit
        return _orig(user_message, default_account)

    ir.try_fast_path = try_fast_path_patched  # type: ignore[assignment]
    ir._press_like_intent_installed = True
    log.info("Makale beğen intent hook kuruldu")
    install_press_like_ui_hooks()


_PRESS_HELP_LINE = (
    "<code>makale beğen</code> · <code>makale beğen aç</code> — gazete oyları"
)


def press_like_dashboard_footer(acc) -> str:
    from .account_config import get_config

    if get_config(acc.name).auto_like_articles:
        return "\n<i>📰✅ Makale otomatik beğenme <b>aktif</b> (~5 dk)</i>"
    return f"\n<i>📰 Gazete: <code>makale beğen aç</code> — otomatik beğeni</i>"


def install_press_like_ui_hooks() -> None:
    """Legacy yardım + dashboard ipucu — telegram_ui'ye dokunmadan."""
    import logging

    from . import telegram_ui as ui

    log = logging.getLogger(__name__)
    if getattr(ui, "_press_like_ui_installed", False):
        return

    legacy = getattr(ui, "_format_help_html_legacy", None)
    if callable(legacy) and not getattr(legacy, "_press_help_patched", False):

        def format_help_legacy_with_press():
            body = legacy()
            if "makale beğen" in body:
                return body
            marker = "<b>Komutlar</b>"
            if marker in body:
                return body.replace(marker, f"{_PRESS_HELP_LINE}\n\n{marker}")
            return f"{body.rstrip()}\n\n{_PRESS_HELP_LINE}\n"

        format_help_legacy_with_press._press_help_patched = True  # type: ignore[attr-defined]
        ui._format_help_html_legacy = format_help_legacy_with_press  # type: ignore[attr-defined]

    _orig_dash = ui.format_dashboard_html

    def format_dashboard_with_press(acc, snap=None):
        body = _orig_dash(acc, snap)
        foot = press_like_dashboard_footer(acc)
        if not foot or foot.strip() in body:
            return body
        return body + foot

    ui.format_dashboard_html = format_dashboard_with_press  # type: ignore[assignment]
    ui._press_like_ui_installed = True
    log.info("Makale beğen UI hook kuruldu (yardım legacy + dashboard)")
