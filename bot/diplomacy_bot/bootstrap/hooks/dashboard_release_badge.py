"""Dashboard sürüm rozeti — explicit bootstrap hook (M4)."""

from __future__ import annotations

import html
import logging

log = logging.getLogger(__name__)


def install_dashboard_release_badge() -> None:
    from diplomacy_bot import telegram_ui as ui
    from diplomacy_bot.bot_updates import release_for_version
    from diplomacy_bot.version import get_version

    if getattr(ui, "_release_badge_installed", False):
        return

    _orig = ui.format_dashboard_html

    def format_dashboard_html_patched(acc, snap=None):
        body = _orig(acc, snap)
        ver = get_version()
        rel = release_for_version(ver)
        if rel:
            codename = html.escape(str(rel.get("codename") or ""))
            badge = f"🆕 v{html.escape(ver)} — {codename}" if codename else f"🆕 v{html.escape(ver)}"
        else:
            badge = f"🆕 v{html.escape(ver)}"
        return f"<i>{badge}</i>\n{body}"

    ui.format_dashboard_html = format_dashboard_html_patched  # type: ignore[assignment]
    ui._release_badge_installed = True
    log.info("Dashboard sürüm rozeti (explicit bootstrap) kuruldu")
