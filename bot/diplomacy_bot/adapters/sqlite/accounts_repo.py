"""accounts tablosu — CRUD ve init."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Iterable

from ...config import LEGACY_AUTH, TELEGRAM_ADMIN_IDS
from ...db_migrate import run_migrations
from .connection import open_connection
from .models import Account, row_to_account
from .snapshots import delete_game_snapshot


def _migrate_legacy_columns(c: sqlite3.Connection) -> None:
    cols = {row[1] for row in c.execute("PRAGMA table_info(accounts)").fetchall()}
    for col, ddl in (
        ("proxy_id", "ALTER TABLE accounts ADD COLUMN proxy_id TEXT DEFAULT 'direct'"),
        ("proxy_url", "ALTER TABLE accounts ADD COLUMN proxy_url TEXT DEFAULT ''"),
        ("status", "ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'active'"),
        ("telegram_user_id", "ALTER TABLE accounts ADD COLUMN telegram_user_id INTEGER DEFAULT 0"),
    ):
        if col not in cols:
            c.execute(ddl)


def _migrate_legacy_owners(c: sqlite3.Connection) -> None:
    if not TELEGRAM_ADMIN_IDS:
        return
    owner = next(iter(TELEGRAM_ADMIN_IDS))
    c.execute(
        "UPDATE accounts SET telegram_user_id=? WHERE COALESCE(telegram_user_id, 0)=0",
        (owner,),
    )


def init_accounts_table() -> None:
    with open_connection() as c:
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
                created_at REAL DEFAULT (strftime('%s','now')),
                telegram_user_id INTEGER DEFAULT 0
            )
            """
        )
        _migrate_legacy_columns(c)
        run_migrations(c)
        _migrate_legacy_owners(c)


def _legacy_owner_id() -> int:
    if TELEGRAM_ADMIN_IDS:
        return next(iter(TELEGRAM_ADMIN_IDS))
    return 0


def bootstrap_legacy() -> Account | None:
    if not LEGACY_AUTH.exists():
        return None
    with open_connection() as c:
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
    from ...account_pool import suggest_proxy

    slot = suggest_proxy(proxy_assignments())
    return add_account(
        name,
        token,
        player_id=data.get("player_id", ""),
        username=data.get("username", name),
        proxy_id=slot.id,
        proxy_url=slot.url,
        telegram_user_id=_legacy_owner_id(),
    )


def find_account_by_player_id(player_id: str) -> Account | None:
    if not player_id:
        return None
    with open_connection() as c:
        row = c.execute(
            "SELECT * FROM accounts WHERE player_id=? LIMIT 1",
            (player_id.strip(),),
        ).fetchone()
    return row_to_account(row) if row else None


def add_account(
    name: str,
    token: str,
    player_id: str = "",
    username: str = "",
    proxy_id: str = "direct",
    proxy_url: str = "",
    *,
    telegram_user_id: int = 0,
) -> Account:
    name = name.strip().lower()
    plain = token.strip()
    existing = get_account(name)
    if existing and existing.telegram_user_id not in (0, telegram_user_id):
        raise ValueError("Bu hesap adı başka bir kullanıcıya ait.")
    if player_id:
        other = find_account_by_player_id(player_id)
        if other and other.name != name and other.telegram_user_id not in (0, telegram_user_id):
            raise ValueError(
                "Bu Diplomacia hesabı başka bir Telegram kullanıcısına bağlı. "
                "Önce o bağlantıyı kaldır veya destekle iletişime geç."
            )
    with open_connection() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(accounts)").fetchall()}
        if "token_enc" in cols:
            c.execute(
                """
                INSERT INTO accounts (
                    name, token, token_enc, player_id, username, proxy_id, proxy_url, telegram_user_id
                )
                VALUES (?, ?, '', ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    token=excluded.token,
                    token_enc='',
                    player_id=excluded.player_id,
                    username=excluded.username,
                    proxy_id=excluded.proxy_id,
                    proxy_url=excluded.proxy_url,
                    telegram_user_id=excluded.telegram_user_id
                """,
                (name, plain, player_id, username, proxy_id, proxy_url, telegram_user_id),
            )
        else:
            c.execute(
                """
                INSERT INTO accounts (
                    name, token, player_id, username, proxy_id, proxy_url, telegram_user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    token=excluded.token,
                    player_id=excluded.player_id,
                    username=excluded.username,
                    proxy_id=excluded.proxy_id,
                    proxy_url=excluded.proxy_url,
                    telegram_user_id=excluded.telegram_user_id
                """,
                (name, plain, player_id, username, proxy_id, proxy_url, telegram_user_id),
            )
    return get_account(name)  # type: ignore[return-value]


def remove_account(name: str, *, telegram_user_id: int | None = None) -> bool:
    name = name.strip().lower()
    if telegram_user_id is not None:
        acc = get_account(name)
        if not acc:
            return False
        if acc.telegram_user_id not in (0, telegram_user_id):
            return False
    delete_game_snapshot(name)
    with open_connection() as c:
        cur = c.execute("DELETE FROM accounts WHERE name=?", (name,))
        return cur.rowcount > 0


def list_accounts() -> list[Account]:
    with open_connection() as c:
        rows = c.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    return [row_to_account(r) for r in rows]


def list_accounts_for_user(telegram_user_id: int) -> list[Account]:
    with open_connection() as c:
        rows = c.execute(
            "SELECT * FROM accounts WHERE telegram_user_id=? ORDER BY name",
            (telegram_user_id,),
        ).fetchall()
    return [row_to_account(r) for r in rows]


def count_accounts_for_user(telegram_user_id: int) -> int:
    with open_connection() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM accounts WHERE telegram_user_id=?",
            (telegram_user_id,),
        ).fetchone()
    return int(row["n"]) if row else 0


def get_account(name: str) -> Account | None:
    with open_connection() as c:
        row = c.execute("SELECT * FROM accounts WHERE name=?", (name.strip().lower(),)).fetchone()
    return row_to_account(row) if row else None


def get_account_for_user(name: str, telegram_user_id: int) -> Account | None:
    acc = get_account(name)
    if not acc:
        return None
    if acc.telegram_user_id == 0:
        return None
    if acc.telegram_user_id != telegram_user_id:
        return None
    return acc


def set_autofarm(name: str, enabled: bool) -> bool:
    with open_connection() as c:
        cur = c.execute(
            "UPDATE accounts SET autofarm=? WHERE name=?",
            (1 if enabled else 0, name.strip().lower()),
        )
        return cur.rowcount > 0


def update_after_farm(name: str, balance: int) -> None:
    now = time.time()
    with open_connection() as c:
        c.execute(
            "UPDATE accounts SET last_farm_at=?, last_balance=? WHERE name=?",
            (now, balance, name.strip().lower()),
        )


def set_runtime_state(name: str, state: str) -> None:
    with open_connection() as c:
        c.execute(
            "UPDATE accounts SET runtime_state=? WHERE name=?",
            (state.strip().lower()[:32], name.strip().lower()),
        )


def autofarm_due(interval_sec: float) -> Iterable[Account]:
    now = time.time()
    with open_connection() as c:
        rows = c.execute("SELECT * FROM accounts WHERE autofarm=1").fetchall()
    for row in rows:
        acc = row_to_account(row)
        if now - acc.last_farm_at >= interval_sec:
            yield acc


def set_proxy(name: str, proxy_id: str, proxy_url: str) -> bool:
    with open_connection() as c:
        cur = c.execute(
            "UPDATE accounts SET proxy_id=?, proxy_url=? WHERE name=?",
            (proxy_id, proxy_url, name.strip().lower()),
        )
        return cur.rowcount > 0


def proxy_assignments() -> dict[str, str]:
    with open_connection() as c:
        rows = c.execute("SELECT name, proxy_id FROM accounts").fetchall()
    return {str(r["name"]): str(r["proxy_id"] or "direct") for r in rows}
