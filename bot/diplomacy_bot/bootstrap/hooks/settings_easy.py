"""Kolay ayarlar UI — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_settings_easy() -> None:
    from diplomacy_bot.settings_easy import install_settings_easy_patch

    install_settings_easy_patch()
    log.info("Settings easy (explicit bootstrap) kuruldu")
