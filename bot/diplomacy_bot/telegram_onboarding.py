"""İlk /start sonrası tek seferlik 3 buton rehberi."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .easy_mode import format_onboarding_guide_html
from .keyboard_prefs import is_reply_keyboard_enabled
from .onboarding_store import is_easy_guide_shown, mark_easy_guide_shown

log = logging.getLogger(__name__)


def onboarding_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Anladım, başlayalım", callback_data="easy:onboard:done")],
            [InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")],
        ]
    )


async def maybe_send_onboarding_guide(
    update: Update,
    *,
    linked: bool,
    telegram_user_id: int,
    account_name: str | None = None,
) -> None:
    if not linked or not update.message:
        return
    if is_easy_guide_shown(telegram_user_id):
        return
    hidden_kb = not is_reply_keyboard_enabled(telegram_user_id)
    war_on = True
    if account_name:
        from .easy_role import war_ui_enabled

        war_on = war_ui_enabled(account_name)
    text = format_onboarding_guide_html(keyboard_hidden=hidden_kb, war_enabled=war_on)
    if not war_on:
        from .easy_role import append_farm_war_tab_note

        text = append_farm_war_tab_note(text)
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=onboarding_markup(),
        disable_notification=False,
    )
    mark_easy_guide_shown(telegram_user_id)
    log.info("Kolay mod rehberi gösterildi uid=%s", telegram_user_id)


async def handle_onboarding_callback(data: str, query, *, uid: int = 0) -> bool:
    if data != "easy:onboard:done":
        return False
    if query and query.message:
        await query.answer("Tamam — butonlara basabilirsin 👍")
        tg_uid = query.from_user.id if query.from_user else uid
        hidden = tg_uid and not is_reply_keyboard_enabled(tg_uid)
        war_on = True
        if tg_uid:
            from .auth import scoped_list_accounts
            from .easy_role import format_onboarding_done_tail, war_ui_enabled

            accs = scoped_list_accounts(tg_uid)
            if accs:
                war_on = war_ui_enabled(accs[0].name)
        else:
            from .easy_role import format_onboarding_done_tail

        tail = format_onboarding_done_tail(war_enabled=war_on, keyboard_hidden=bool(hidden))
        await query.edit_message_text(
            f"✅ <b>Hazırsın!</b>\n\n"
            f"Şimdi {tail}",
            parse_mode="HTML",
        )
    return True
