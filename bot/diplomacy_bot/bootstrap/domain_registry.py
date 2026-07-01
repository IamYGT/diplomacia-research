"""M4 domain hook registry — connect, fleet, autofarm, scope."""

from __future__ import annotations

import logging
from collections.abc import Callable

from .hooks.account_scope_domain import install_account_scope_domain
from .hooks.ai_agent_fast import install_ai_agent_fast_paths
from .hooks.connect_domain import install_connect_domain
from .hooks.fleet_domain import install_fleet_domain
from .hooks.token_refresh_domain import install_token_refresh_domain
from .hooks.war_contribute_domain import install_war_contribute_domain
from .hooks.work_mode_domain import install_work_mode_domain

log = logging.getLogger(__name__)

_DOMAIN_HOOKS: tuple[Callable[[], None], ...] = (
    install_war_contribute_domain,
    install_ai_agent_fast_paths,
    install_connect_domain,
    install_work_mode_domain,
    install_account_scope_domain,
    install_token_refresh_domain,
    install_fleet_domain,
)
_INSTALLED = False


def install_domain_hooks() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    for hook in _DOMAIN_HOOKS:
        hook()
    _INSTALLED = True
    log.info("Domain bootstrap hooks kuruldu (%s)", len(_DOMAIN_HOOKS))
