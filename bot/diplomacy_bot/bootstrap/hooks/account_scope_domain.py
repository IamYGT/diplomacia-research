"""Hesap scope domain — explicit bootstrap hook (M4 domain)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_account_scope_domain() -> None:
    from diplomacy_bot.account_scope import install_account_scope_hooks

    install_account_scope_hooks()
    log.info("Account scope domain (bootstrap) kuruldu")
