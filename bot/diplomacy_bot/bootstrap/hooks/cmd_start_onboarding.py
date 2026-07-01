""" /start onboarding — explicit bootstrap hook (M4). """

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_cmd_start_onboarding() -> None:
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.keyboard_reply import user_reply_keyboard
    from diplomacy_bot.telegram_helpers import user_required
    from diplomacy_bot.telegram_onboarding import maybe_send_onboarding_guide

    if getattr(ta, "_onboarding_start_installed", False):
        return

    _orig = ta.cmd_start

    @user_required
    async def cmd_start_patched(update, context):
        uid = ta._uid(update)
        default = ta._default_account(context, uid)
        acc = ta.resolve_account(default, uid) if default else None
        linked = acc is not None
        async with user_reply_keyboard(uid):
            await _orig(update, context)
        await maybe_send_onboarding_guide(
            update, linked=linked, telegram_user_id=uid, account_name=acc.name if acc else None
        )

    ta.cmd_start = cmd_start_patched
    ta._onboarding_start_installed = True
    log.info("/start onboarding (explicit bootstrap) kuruldu")
