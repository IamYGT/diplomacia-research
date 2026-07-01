"""Fleet Telegram action guard — stale side-effect buttons."""

from __future__ import annotations

from .telegram_navigation import STALE_NAVIGATION_AFTER_SEC, message_age_seconds


def is_stale_fleet_action(query, *, stale_after_sec: int = STALE_NAVIGATION_AFTER_SEC) -> bool:
    message = getattr(query, "message", None)
    age = message_age_seconds(getattr(message, "date", None))
    return age is None or age >= stale_after_sec


async def reject_stale_fleet_action(query, label: str) -> bool:
    if not query or not getattr(query, "message", None) or not is_stale_fleet_action(query):
        return False
    from .fleet_ui_markup import fleet_nav_inline_markup

    await query.message.reply_text(
        f"⏳ Eski <b>{label}</b> butonu. Güncel panelden tekrar seç.",
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )
    return True
