"""bot_sessions tablosu."""

from __future__ import annotations

import time

from .connection import open_connection


def get_session(telegram_user_id: int) -> dict | None:
    with open_connection() as c:
        row = c.execute(
            "SELECT * FROM bot_sessions WHERE telegram_user_id=?",
            (telegram_user_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_session(
    telegram_user_id: int,
    *,
    active_account: str | None = None,
    last_menu: str | None = None,
    pending_connect: bool | None = None,
) -> None:
    now = time.time()
    existing = get_session(telegram_user_id) or {}
    acc = active_account if active_account is not None else existing.get("active_account")
    menu = last_menu if last_menu is not None else existing.get("last_menu", "")
    pending = (
        int(pending_connect)
        if pending_connect is not None
        else int(existing.get("pending_connect") or 0)
    )
    with open_connection() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, active_account, last_menu, pending_connect, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                active_account=excluded.active_account,
                last_menu=excluded.last_menu,
                pending_connect=excluded.pending_connect,
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, acc, menu or "", pending, now),
        )


def clear_session_pending(telegram_user_id: int) -> None:
    upsert_session(telegram_user_id, pending_connect=False)
