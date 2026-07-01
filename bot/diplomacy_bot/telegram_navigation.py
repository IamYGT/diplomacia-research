"""Telegram navigation freshness rules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

STALE_NAVIGATION_AFTER_SEC = 180

NAVIGATION_CALLBACKS = frozenset(
    {
        "dash:home",
        "menu:accounts",
        "menu:connect",
        "menu:extras",
        "menu:fleet",
        "menu:settings",
    }
)


def is_navigation_callback(data: str) -> bool:
    """Callbacks that open another screen instead of performing an action."""
    return (
        data in NAVIGATION_CALLBACKS
        or data.startswith("menu:accounts:")
        or data.startswith("nav:account:")
        or data.startswith("role:pick:")
        or data.startswith("fleet:menu:")
        or data.startswith("easy:")
        or data.startswith("mission:")
    )


def message_age_seconds(message_date: datetime | None, *, now: datetime | None = None) -> float | None:
    if message_date is None:
        return None
    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)
    current = now or datetime.now(message_date.tzinfo or timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age = (current.astimezone(timezone.utc) - message_date.astimezone(timezone.utc)).total_seconds()
    return max(0.0, age)


def callback_prefers_fresh_reply(
    data: str,
    query: Any,
    *,
    stale_after_sec: int = STALE_NAVIGATION_AFTER_SEC,
    now: datetime | None = None,
) -> bool:
    """Return True when a navigation callback should open a visible new panel."""
    if not is_navigation_callback(data):
        return False
    message = getattr(query, "message", None)
    age = message_age_seconds(getattr(message, "date", None), now=now)
    if age is None:
        return True
    return age >= stale_after_sec


async def reply_or_edit_callback(
    query: Any,
    data: str,
    text: str,
    **kwargs: Any,
) -> Any:
    """Edit recent callback messages, but open a visible reply for stale panels."""
    if callback_prefers_fresh_reply(data, query):
        message = getattr(query, "message", None)
        if message is not None:
            return await message.reply_text(text, **kwargs)
    return await query.edit_message_text(text, **kwargs)
