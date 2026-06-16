"""SQLite şema sürümü — sıralı migration."""

from __future__ import annotations

import sqlite3
from typing import Callable

CURRENT_SCHEMA_VERSION = 5

MigrationFn = Callable[[sqlite3.Connection], None]


def _table_exists(c: sqlite3.Connection, name: str) -> bool:
    row = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _column_exists(c: sqlite3.Connection, table: str, col: str) -> bool:
    cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
    return col in cols


def _migration_1_indexes(c: sqlite3.Connection) -> None:
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_accounts_telegram_user ON accounts(telegram_user_id)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_accounts_player_id ON accounts(player_id)"
    )


def _migration_2_persistence_tables(c: sqlite3.Connection) -> None:
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS game_snapshots (
            account_name TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            fetched_at REAL NOT NULL,
            stale_after REAL NOT NULL
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT,
            telegram_user_id INTEGER DEFAULT 0,
            action TEXT NOT NULL,
            result TEXT,
            success INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s','now'))
        )
        """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_action_log_account
        ON action_log(account_name, created_at DESC)
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_sessions (
            telegram_user_id INTEGER PRIMARY KEY,
            active_account TEXT,
            last_menu TEXT DEFAULT '',
            pending_connect INTEGER DEFAULT 0,
            updated_at REAL DEFAULT (strftime('%s','now'))
        )
        """
    )


def _migration_3_runtime_state(c: sqlite3.Connection) -> None:
    """runtime_state kolonu — JWT şifreleme yok."""
    if not _table_exists(c, "accounts"):
        return
    if not _column_exists(c, "accounts", "runtime_state"):
        c.execute(
            "ALTER TABLE accounts ADD COLUMN runtime_state TEXT DEFAULT 'idle'"
        )
    if not _column_exists(c, "accounts", "token_enc"):
        c.execute("ALTER TABLE accounts ADD COLUMN token_enc TEXT DEFAULT ''")


def _migration_3_token_enc(c: sqlite3.Connection) -> None:
    """Eski ad — sadece kolon ekleme (şifreleme kaldırıldı)."""
    _migration_3_runtime_state(c)


def _migration_4_snapshot_indexes(c: sqlite3.Connection) -> None:
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_game_snapshots_fetched
        ON game_snapshots(fetched_at DESC)
        """
    )


def _migration_5_plaintext_tokens(c: sqlite3.Connection) -> None:
    """Şifreli token'ları düz eyJ… olarak geri yaz."""
    if not _table_exists(c, "accounts"):
        return
    try:
        from .token_crypto import decrypt_token
    except ImportError:
        return
    rows = c.execute("SELECT name, token, token_enc FROM accounts").fetchall()
    for row in rows:
        name = row["name"]
        enc = (row["token_enc"] or "").strip()
        plain = (row["token"] or "").strip()
        if enc:
            jwt = decrypt_token(enc)
            if jwt:
                c.execute(
                    "UPDATE accounts SET token=?, token_enc='' WHERE name=?",
                    (jwt, name),
                )
        elif plain == "__enc__":
            continue
        elif plain.startswith("eyJ"):
            c.execute(
                "UPDATE accounts SET token_enc='' WHERE name=?",
                (name,),
            )


MIGRATIONS: list[tuple[int, MigrationFn]] = [
    (1, _migration_1_indexes),
    (2, _migration_2_persistence_tables),
    (3, _migration_3_token_enc),
    (4, _migration_4_snapshot_indexes),
    (5, _migration_5_plaintext_tokens),
]


def run_migrations(c: sqlite3.Connection) -> None:
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at REAL DEFAULT (strftime('%s','now'))
        )
        """
    )
    applied = {
        int(r["version"])
        for r in c.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for version, fn in MIGRATIONS:
        if version in applied:
            continue
        fn(c)
        c.execute(
            "INSERT INTO schema_migrations(version) VALUES (?)",
            (version,),
        )
    c.commit()
