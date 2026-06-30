"""Tek seferlik kolay mod rehberi — bot_sessions.easy_guide_shown."""

from __future__ import annotations

import time

from .store import _conn, get_session, init_db


def is_easy_guide_shown(telegram_user_id: int) -> bool:
    init_db()
    sess = get_session(telegram_user_id) or {}
    return bool(int(sess.get("easy_guide_shown") or 0))


def mark_easy_guide_shown(telegram_user_id: int) -> None:
    init_db()
    now = time.time()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, easy_guide_shown, updated_at)
            VALUES (?, 1, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                easy_guide_shown=1,
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, now),
        )
