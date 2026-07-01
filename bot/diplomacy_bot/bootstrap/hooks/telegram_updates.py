"""Güncellemeler sayfası — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_telegram_updates() -> None:
    from diplomacy_bot.telegram_updates import install_updates_post_init

    install_updates_post_init()
    log.info("Telegram updates (explicit bootstrap) kuruldu")
