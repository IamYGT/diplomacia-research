"""Uid-scoped reply keyboard — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_reply_keyboard_entries() -> None:
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.keyboard_reply import patch_all_handler_keyboards, user_reply_keyboard

    if getattr(ta, "_reply_keyboard_entries_installed", False):
        return

    patch_all_handler_keyboards()

    _orig_dispatch = ta._dispatch_menu

    async def _dispatch_menu_patched(update, context, action):
        uid = ta._uid(update)
        async with user_reply_keyboard(uid):
            await _orig_dispatch(update, context, action)

    ta._dispatch_menu = _dispatch_menu_patched
    ta._reply_keyboard_entries_installed = True
    log.info("Reply klavye uid (explicit bootstrap) kuruldu")
