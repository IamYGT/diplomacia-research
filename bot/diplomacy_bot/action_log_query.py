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


def count_action_results_since(
    *,
    account_names: list[str],
    action: str,
    since_unix: float,
) -> dict[str, int]:
    names = [n.strip().lower() for n in account_names if n.strip()]
    if not names:
        return {}
    placeholders = ",".join("?" * len(names))
    sql = f"""
        SELECT result, COUNT(*) AS n FROM action_log
        WHERE account_name IN ({placeholders})
          AND action = ?
          AND created_at >= ?
        GROUP BY result
    """
    params: list = [*names, action[:64], since_unix]
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return {str(row["result"] or ""): int(row["n"] or 0) for row in rows}
