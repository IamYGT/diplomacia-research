"""Token süre alanları — store.py'ye dokunmadan DB güncelleme."""

from __future__ import annotations

import time

from .jwt_meta import token_exp_unix


def _conn():
    from .store import _conn as store_conn

    return store_conn()


def ensure_token_meta_columns() -> None:
    from .db_migrate import run_migrations

    with _conn() as c:
        run_migrations(c)


def record_token_saved(account_name: str, token: str) -> None:
    """Bağlantı/yenileme sonrası exp zaman damgasını yaz."""
    ensure_token_meta_columns()
    name = account_name.strip().lower()
    now = time.time()
    exp = token_exp_unix(token)
    with _conn() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(accounts)").fetchall()}
        if "token_exp_at" in cols and "last_token_refresh_at" in cols:
            c.execute(
                """
                UPDATE accounts
                SET token_exp_at=?, last_token_refresh_at=?
                WHERE name=?
                """,
                (exp, now, name),
            )
        elif "token_exp_at" in cols:
            c.execute("UPDATE accounts SET token_exp_at=? WHERE name=?", (exp, name))


def get_token_exp_at(account_name: str) -> float | None:
    ensure_token_meta_columns()
    name = account_name.strip().lower()
    with _conn() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(accounts)").fetchall()}
        if "token_exp_at" not in cols:
            return None
        row = c.execute(
            "SELECT token_exp_at FROM accounts WHERE name=?",
            (name,),
        ).fetchone()
    if not row or row["token_exp_at"] is None:
        return None
    try:
        return float(row["token_exp_at"])
    except (TypeError, ValueError):
        return None
