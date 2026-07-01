"""action_log tablosu."""

from __future__ import annotations

from .connection import open_connection


def log_action(
    action: str,
    *,
    account_name: str = "",
    telegram_user_id: int = 0,
    result: str = "",
    success: bool = True,
) -> None:
    with open_connection() as c:
        c.execute(
            """
            INSERT INTO action_log (account_name, telegram_user_id, action, result, success)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                account_name.strip().lower() if account_name else "",
                telegram_user_id,
                action[:64],
                (result or "")[:500],
                1 if success else 0,
            ),
        )


def recent_actions(account_name: str, limit: int = 10) -> list[dict]:
    with open_connection() as c:
        rows = c.execute(
            """
            SELECT action, result, success, created_at, telegram_user_id
            FROM action_log
            WHERE account_name=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (account_name.strip().lower(), limit),
        ).fetchall()
    return [dict(r) for r in rows]
