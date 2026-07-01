"""Work mode domain — explicit bootstrap hook (M4 domain)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_work_mode_domain() -> None:
    from diplomacy_bot.work_mode_hooks import install_work_mode_hooks

    install_work_mode_hooks()
    log.info("Work mode domain (bootstrap) kuruldu")
