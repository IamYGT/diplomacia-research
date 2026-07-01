"""Connect domain — explicit bootstrap hook (M4 domain)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_connect_domain() -> None:
    from diplomacy_bot.connect_hooks import install_connect_hooks
    from diplomacy_bot.connect_save import wire_save_account

    wire_save_account()
    install_connect_hooks()
    log.info("Connect domain (bootstrap) kuruldu")
