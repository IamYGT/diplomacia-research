"""Görev + hesap komutları — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_mission_account_hooks() -> None:
    from diplomacy_bot import callbacks as cb
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.telegram_account_cmds import register_account_handlers
    from diplomacy_bot.telegram_mission import (
        handle_mission_callback,
        register_mission_commands_extra,
        register_mission_handlers,
    )

    if getattr(ta, "_mission_hook_installed", False):
        return

    _orig_post = ta._post_init

    async def _post_init(application):
        register_mission_commands_extra()
        await _orig_post(application)
        register_mission_handlers(application)
        register_account_handlers(application)

    ta._post_init = _post_init

    _orig_cb = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if await handle_mission_callback(data, query, uid):
            return
        return await _orig_cb(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched

    ta._mission_hook_installed = True
    log.info("Görev + setmain (explicit bootstrap) kuruldu")
