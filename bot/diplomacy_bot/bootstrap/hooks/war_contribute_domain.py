"""War contribute shims — domain bootstrap (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_war_contribute_domain() -> None:
    from diplomacy_bot.war_contribute_format import patch_war_contribute_shims

    patch_war_contribute_shims()
    log.info("War contribute domain (bootstrap) kuruldu")
