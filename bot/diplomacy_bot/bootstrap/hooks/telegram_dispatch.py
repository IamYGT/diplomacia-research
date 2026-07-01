"""Kolay mod klavye dispatch — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_telegram_dispatch() -> None:
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.telegram_easy import handle_easy_menu_action

    if getattr(ta, "_easy_dispatch_installed", False):
        return

    _orig = ta._dispatch_menu

    async def _dispatch_menu(update, context, action):
        if await handle_easy_menu_action(action, update, context):
            return
        await _orig(update, context, action)

    ta._dispatch_menu = _dispatch_menu
    ta._easy_dispatch_installed = True
    log.info("Kolay mod dispatch (explicit bootstrap) kuruldu")
