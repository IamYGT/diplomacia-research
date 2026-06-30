"""Kullanıcı başına tek dashboard mesajı — chat/message pin."""

from __future__ import annotations

import logging
import time

from telegram import Bot

from .store import _conn, get_session, init_db

log = logging.getLogger(__name__)


def get_dashboard_pin(telegram_user_id: int) -> tuple[int, int] | None:
    init_db()
    sess = get_session(telegram_user_id) or {}
    chat_id = sess.get("dashboard_chat_id")
    msg_id = sess.get("dashboard_message_id")
    if chat_id is None or msg_id is None:
        return None
    try:
        c, m = int(chat_id), int(msg_id)
    except (TypeError, ValueError):
        return None
    if c <= 0 or m <= 0:
        return None
    return c, m


def set_dashboard_pin(telegram_user_id: int, chat_id: int, message_id: int) -> None:
    init_db()
    now = time.time()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, dashboard_chat_id, dashboard_message_id, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                dashboard_chat_id=excluded.dashboard_chat_id,
                dashboard_message_id=excluded.dashboard_message_id,
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, int(chat_id), int(message_id), now),
        )


def clear_dashboard_pin(telegram_user_id: int) -> None:
    init_db()
    now = time.time()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, dashboard_chat_id, dashboard_message_id, updated_at)
            VALUES (?, 0, 0, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                dashboard_chat_id=0,
                dashboard_message_id=0,
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, now),
        )


async def delete_pinned_dashboard(bot: Bot, telegram_user_id: int) -> None:
    pin = get_dashboard_pin(telegram_user_id)
    if not pin:
        return
    chat_id, msg_id = pin
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception as e:
        log.debug("dashboard delete skip uid=%s: %s", telegram_user_id, e)
    clear_dashboard_pin(telegram_user_id)
