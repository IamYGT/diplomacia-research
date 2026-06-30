"""Token yenileme bekleyen hesap — DB oturum alanı."""

from __future__ import annotations

import time

from .store import _conn, get_session, init_db


def set_pending_token_account(telegram_user_id: int, account_name: str) -> None:
    init_db()
    now = time.time()
    name = account_name.strip().lower()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, pending_connect, pending_token_account, updated_at)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                pending_connect=1,
                pending_token_account=excluded.pending_token_account,
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, name, now),
        )


def get_pending_token_account(telegram_user_id: int) -> str | None:
    init_db()
    row = get_session(telegram_user_id) or {}
    if not int(row.get("pending_connect") or 0):
        return None
    name = str(row.get("pending_token_account") or "").strip().lower()
    return name or None


def clear_pending_token_account(telegram_user_id: int) -> None:
    init_db()
    now = time.time()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, pending_connect, pending_token_account, updated_at)
            VALUES (?, 0, '', ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                pending_connect=0,
                pending_token_account='',
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, now),
        )
