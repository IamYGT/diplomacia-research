"""Dashboard can/hap banner — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_health_sync_ui() -> None:
    from diplomacy_bot.health_sync import install_health_sync_hooks

    install_health_sync_hooks()
    log.info("Health sync UI (explicit bootstrap) kuruldu")
