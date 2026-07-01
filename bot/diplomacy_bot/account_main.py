from __future__ import annotations

import time

from .store import _conn, get_session, init_db


def get_main_account_name(telegram_user_id: int | None = None) -> str | None:
    """Ana hesap — önce session, sonra kullanıcıya özel is_main bayrağı."""
    init_db()
    if telegram_user_id:
        sess = get_session(telegram_user_id) or {}
        main = (sess.get("main_account") or "").strip().lower()
        if main:
            return main
    with _conn() as c:
        if telegram_user_id:
            row = c.execute(
                "SELECT name FROM accounts WHERE is_main=1 AND telegram_user_id=? ORDER BY id LIMIT 1",
                (telegram_user_id,),
            ).fetchone()
        else:
            row = c.execute(
                "SELECT name FROM accounts WHERE is_main=1 ORDER BY id LIMIT 1"
            ).fetchone()
    return str(row["name"]).lower() if row else None


def set_main_account(account_name: str, *, telegram_user_id: int | None = None) -> None:
    """Ana hesap — kullanıcı başına is_main + session."""
    from .auth import resolve_account

    init_db()
    name = account_name.strip().lower()
    if telegram_user_id and not resolve_account(name, telegram_user_id):
        raise ValueError("Hesap bu kullanıcıya ait değil")
    with _conn() as c:
        if telegram_user_id:
            c.execute("UPDATE accounts SET is_main=0 WHERE telegram_user_id=?", (telegram_user_id,))
        else:
            c.execute("UPDATE accounts SET is_main=0")
        c.execute("UPDATE accounts SET is_main=1 WHERE LOWER(name)=?", (name,))
        if telegram_user_id:
            c.execute(
                """
                INSERT INTO bot_sessions (telegram_user_id, main_account, active_account, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    main_account=excluded.main_account,
                    active_account=excluded.active_account,
                    updated_at=excluded.updated_at
                """,
                (telegram_user_id, name, name, time.time()),
            )
