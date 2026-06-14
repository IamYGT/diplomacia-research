from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import DB_PATH, LEGACY_AUTH


@dataclass
class Account:
    id: int
    name: str
    token: str
    player_id: str
    username: str
    autofarm: bool
    last_farm_at: float
    last_balance: int
    proxy_id: str
    proxy_url: str
    status: str


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    from .account_config import init_config_table

    init_config_table()
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                token TEXT NOT NULL,
                player_id TEXT,
                username TEXT,
                autofarm INTEGER DEFAULT 0,
                last_farm_at REAL DEFAULT 0,
                last_balance INTEGER DEFAULT 0,
                proxy_id TEXT DEFAULT 'direct',
                proxy_url TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at REAL DEFAULT (strftime('%s','now'))
            )
            """
        )
        _migrate_columns(c)


def _migrate_columns(c: sqlite3.Connection) -> None:
    cols = {row[1] for row in c.execute("PRAGMA table_info(accounts)").fetchall()}
    for col, ddl in (
        ("proxy_id", "ALTER TABLE accounts ADD COLUMN proxy_id TEXT DEFAULT 'direct'"),
        ("proxy_url", "ALTER TABLE accounts ADD COLUMN proxy_url TEXT DEFAULT ''"),
        ("status", "ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'active'"),
    ):
        if col not in cols:
            c.execute(ddl)


def bootstrap_legacy() -> Account | None:
    if not LEGACY_AUTH.exists():
        return None
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()
        if row and row["n"] > 0:
            return None
    raw = LEGACY_AUTH.read_text(encoding="utf-8").strip()
    if raw.startswith("eyJ"):
        token = raw.splitlines()[0].strip()
        data: dict = {}
    else:
        data = json.loads(raw)
        token = data.get("token", "")
    if not token:
        return None
    name = (data.get("username") or "ygt").strip().lower().replace(" ", "_")[:32] or "ygt"
    from .account_pool import suggest_proxy

    assignments = proxy_assignments()
    slot = suggest_proxy(assignments)
    return add_account(
        name,
        token,
        player_id=data.get("player_id", ""),
        username=data.get("username", name),
        proxy_id=slot.id,
        proxy_url=slot.url,
    )


def add_account(
    name: str,
    token: str,
    player_id: str = "",
    username: str = "",
    proxy_id: str = "direct",
    proxy_url: str = "",
) -> Account:
    name = name.strip().lower()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO accounts (name, token, player_id, username, proxy_id, proxy_url)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                token=excluded.token,
                player_id=excluded.player_id,
                username=excluded.username,
                proxy_id=excluded.proxy_id,
                proxy_url=excluded.proxy_url
            """,
            (name, token.strip(), player_id, username, proxy_id, proxy_url),
        )
    return get_account(name)  # type: ignore[return-value]


def remove_account(name: str) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM accounts WHERE name=?", (name.strip().lower(),))
        return cur.rowcount > 0


def list_accounts() -> list[Account]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    return [_row_to_account(r) for r in rows]


def get_account(name: str) -> Account | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM accounts WHERE name=?", (name.strip().lower(),)).fetchone()
    return _row_to_account(row) if row else None


def set_autofarm(name: str, enabled: bool) -> bool:
    with _conn() as c:
        cur = c.execute("UPDATE accounts SET autofarm=? WHERE name=?", (1 if enabled else 0, name.strip().lower()))
        return cur.rowcount > 0


def update_after_farm(name: str, balance: int) -> None:
    now = time.time()
    with _conn() as c:
        c.execute(
            "UPDATE accounts SET last_farm_at=?, last_balance=? WHERE name=?",
            (now, balance, name.strip().lower()),
        )


def autofarm_due(interval_sec: float) -> Iterable[Account]:
    now = time.time()
    with _conn() as c:
        rows = c.execute("SELECT * FROM accounts WHERE autofarm=1").fetchall()
    for row in rows:
        acc = _row_to_account(row)
        if now - acc.last_farm_at >= interval_sec:
            yield acc


def set_proxy(name: str, proxy_id: str, proxy_url: str) -> bool:
    with _conn() as c:
        cur = c.execute(
            "UPDATE accounts SET proxy_id=?, proxy_url=? WHERE name=?",
            (proxy_id, proxy_url, name.strip().lower()),
        )
        return cur.rowcount > 0


def proxy_assignments() -> dict[str, str]:
    with _conn() as c:
        rows = c.execute("SELECT name, proxy_id FROM accounts").fetchall()
    return {str(r["name"]): str(r["proxy_id"] or "direct") for r in rows}


def _row_to_account(row: sqlite3.Row) -> Account:
    return Account(
        id=row["id"],
        name=row["name"],
        token=row["token"],
        player_id=row["player_id"] or "",
        username=row["username"] or "",
        autofarm=bool(row["autofarm"]),
        last_farm_at=float(row["last_farm_at"] or 0),
        last_balance=int(row["last_balance"] or 0),
        proxy_id=str(row["proxy_id"] or "direct") if "proxy_id" in row.keys() else "direct",
        proxy_url=str(row["proxy_url"] or "") if "proxy_url" in row.keys() else "",
        status=str(row["status"] or "active") if "status" in row.keys() else "active",
    )
