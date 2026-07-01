"""Coach dashboard — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_dashboard_coach() -> None:
    from diplomacy_bot.dashboard_coach import install_dashboard_coach_patch

    install_dashboard_coach_patch()
    log.info("Dashboard coach (explicit bootstrap) kuruldu")
