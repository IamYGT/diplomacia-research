"""Fleet komuta domain — explicit bootstrap hook (M4 domain)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_fleet_domain() -> None:
    from diplomacy_bot.fleet_command_hooks import install_fleet_command_hooks

    install_fleet_command_hooks()
    log.info("Fleet domain (bootstrap) kuruldu")
