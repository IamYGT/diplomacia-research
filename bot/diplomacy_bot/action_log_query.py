"""action_log sorguları — store.py boyut limiti için ayrıldı."""

from __future__ import annotations

import sqlite3

from .config import DB_PATH


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def count_actions_since(
    *,
    account_names: list[str],
    action: str,
    since_unix: float,
    success_only: bool = True,
) -> int:
    names = [n.strip().lower() for n in account_names if n.strip()]
    if not names:
        return 0
    placeholders = ",".join("?" * len(names))
    sql = f"""
        SELECT COUNT(*) FROM action_log
        WHERE account_name IN ({placeholders})
          AND action = ?
          AND created_at >= ?
    """
    params: list = [*names, action[:64], since_unix]
    if success_only:
        sql += " AND success = 1"
    with _conn() as c:
        row = c.execute(sql, params).fetchone()
    return int(row[0] if row else 0)
