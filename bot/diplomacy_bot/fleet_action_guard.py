"""Fleet Telegram action guard — stale side-effect buttons."""

from __future__ import annotations

from .telegram_navigation import STALE_NAVIGATION_AFTER_SEC, message_age_seconds


def is_stale_fleet_action(query, *, stale_after_sec: int = STALE_NAVIGATION_AFTER_SEC) -> bool:
    message = getattr(query, "message", None)
    age = message_age_seconds(getattr(message, "date", None))
    return age is None or age >= stale_after_sec


def _stale_action_text(label: str, telegram_user_id: int | None) -> str:
    text = (
        f"⏳ Eski <b>{label}</b> butonu.\n"
        "Yeni mesajdaki panelden devam et; eski Telegram mesajları görünür sonucu kaçırabilir."
    )
    if telegram_user_id is None:
        return text
    try:
        from .fleet_status import format_fleet_ops_status

        status = format_fleet_ops_status(telegram_user_id, detailed=False)
    except Exception:
        status = ""
    if not status:
        return text
    return f"{text}\n\n{status}"


async def reject_stale_fleet_action(query, label: str, telegram_user_id: int | None = None) -> bool:
    if not query or not getattr(query, "message", None) or not is_stale_fleet_action(query):
        return False
    from .fleet_ui_markup import fleet_nav_inline_markup

    await query.message.reply_text(
        _stale_action_text(label, telegram_user_id),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )
    return True
