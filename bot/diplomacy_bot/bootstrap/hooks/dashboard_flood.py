"""Dashboard flood önleme — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_dashboard_flood() -> None:
    from diplomacy_bot.dashboard_flood import install_dashboard_flood_patch

    install_dashboard_flood_patch()
    log.info("Dashboard flood (explicit bootstrap) kuruldu")
