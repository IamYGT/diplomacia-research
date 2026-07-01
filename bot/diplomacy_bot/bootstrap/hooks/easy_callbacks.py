"""Kolay mod callback + komut — explicit bootstrap hook (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_easy_callbacks() -> None:
    from diplomacy_bot import callbacks as cb
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.telegram_easy import (
        handle_easy_callback,
        register_easy_commands_extra,
        register_easy_handlers,
    )

    if getattr(ta, "_easy_hook_installed", False):
        return

    register_easy_commands_extra()

    _orig_post = ta._post_init

    async def _post_init(application):
        await _orig_post(application)
        register_easy_handlers(application)

    ta._post_init = _post_init

    _orig_cb = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if await handle_easy_callback(data, query, uid):
            return
        return await _orig_cb(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched

    ta._easy_hook_installed = True
    log.info("Kolay mod callback (explicit bootstrap) kuruldu")
