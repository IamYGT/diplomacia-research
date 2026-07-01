"""Savaş/Seyahat sekmeleri — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_telegram_tabs() -> None:
    from diplomacy_bot.telegram_tabs import install_tab_hooks

    install_tab_hooks()
    log.info("Telegram tabs (explicit bootstrap) kuruldu")
