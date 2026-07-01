"""Token recovery — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_token_recovery() -> None:
    from diplomacy_bot.token_recovery_hooks import install_token_recovery_hooks

    install_token_recovery_hooks()
    log.info("Token recovery (explicit bootstrap) kuruldu")
