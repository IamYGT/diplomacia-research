"""Alttaki reply klavye — kullanıcı başına aç/kapa."""

from __future__ import annotations

import time

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

from .easy_mode import main_reply_keyboard_easy
from .store import _conn, get_session, init_db


def is_reply_keyboard_enabled(telegram_user_id: int) -> bool:
    init_db()
    sess = get_session(telegram_user_id) or {}
    if "reply_keyboard_enabled" not in sess or sess.get("reply_keyboard_enabled") is None:
        return True
    return bool(int(sess.get("reply_keyboard_enabled") or 0))


def set_reply_keyboard_enabled(telegram_user_id: int, enabled: bool) -> None:
    init_db()
    now = time.time()
    val = 1 if enabled else 0
    with _conn() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, reply_keyboard_enabled, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                reply_keyboard_enabled=excluded.reply_keyboard_enabled,
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, val, now),
        )


def toggle_reply_keyboard(telegram_user_id: int) -> bool:
    new_val = not is_reply_keyboard_enabled(telegram_user_id)
    set_reply_keyboard_enabled(telegram_user_id, new_val)
    return new_val


def reply_keyboard_for_user(telegram_user_id: int | None) -> ReplyKeyboardMarkup | ReplyKeyboardRemove | None:
    """None = mevcut klavyeyi değiştirme (inline-only mesajlar)."""
    if telegram_user_id is None:
        return main_reply_keyboard_easy()
    if is_reply_keyboard_enabled(telegram_user_id):
        return main_reply_keyboard_easy()
    return ReplyKeyboardRemove()


def keyboard_toggle_label(telegram_user_id: int) -> str:
    return "⌨️ Alttaki butonlar: Açık" if is_reply_keyboard_enabled(telegram_user_id) else "⌨️ Alttaki butonlar: Kapalı"
