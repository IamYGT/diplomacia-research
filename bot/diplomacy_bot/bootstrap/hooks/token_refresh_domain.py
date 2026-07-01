"""Token refresh domain — explicit bootstrap hook (M4 domain)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_token_refresh_domain() -> None:
    from diplomacy_bot.token_refresh_hooks import install_token_refresh_hooks

    install_token_refresh_hooks()
    log.info("Token refresh domain (bootstrap) kuruldu")
