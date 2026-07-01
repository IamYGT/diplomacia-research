"""SQLite şema sürümü — sıralı migration."""

from __future__ import annotations

import sqlite3
from typing import Callable

CURRENT_SCHEMA_VERSION = 12

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


def _migration_10_dashboard_pin(c: sqlite3.Connection) -> None:
    if not _table_exists(c, "bot_sessions"):
        return
    if not _column_exists(c, "bot_sessions", "dashboard_chat_id"):
        c.execute(
            "ALTER TABLE bot_sessions ADD COLUMN dashboard_chat_id INTEGER DEFAULT 0"
        )
    if not _column_exists(c, "bot_sessions", "dashboard_message_id"):
        c.execute(
            "ALTER TABLE bot_sessions ADD COLUMN dashboard_message_id INTEGER DEFAULT 0"
        )


def _migration_9_reply_keyboard_pref(c: sqlite3.Connection) -> None:
    if not _table_exists(c, "bot_sessions"):
        return
    if not _column_exists(c, "bot_sessions", "reply_keyboard_enabled"):
        c.execute(
            "ALTER TABLE bot_sessions ADD COLUMN reply_keyboard_enabled INTEGER DEFAULT 1"
        )


def _migration_8_easy_guide(c: sqlite3.Connection) -> None:
    if not _table_exists(c, "bot_sessions"):
        return
    if not _column_exists(c, "bot_sessions", "easy_guide_shown"):
        c.execute(
            "ALTER TABLE bot_sessions ADD COLUMN easy_guide_shown INTEGER DEFAULT 0"
        )


def _migration_7_account_missions(c: sqlite3.Connection) -> None:
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS account_missions (
            account_name TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            plan_json TEXT NOT NULL,
            runtime_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_account_missions_status ON account_missions(status)"
    )


def _migration_6_main_account(c: sqlite3.Connection) -> None:
    if not _table_exists(c, "accounts"):
        return
    if not _column_exists(c, "accounts", "is_main"):
        c.execute("ALTER TABLE accounts ADD COLUMN is_main INTEGER DEFAULT 0")
    if not _column_exists(c, "bot_sessions", "main_account"):
        c.execute("ALTER TABLE bot_sessions ADD COLUMN main_account TEXT DEFAULT ''")
    # Varsayılan ana hesap: ygt (varsa)
    row = c.execute(
        "SELECT name FROM accounts WHERE LOWER(name)='ygt' LIMIT 1"
    ).fetchone()
    if row:
        c.execute("UPDATE accounts SET is_main=0")
        c.execute("UPDATE accounts SET is_main=1 WHERE LOWER(name)='ygt'")


def _migration_11_pending_token_account(c: sqlite3.Connection) -> None:
    if not _table_exists(c, "bot_sessions"):
        return
    if not _column_exists(c, "bot_sessions", "pending_token_account"):
        c.execute(
            "ALTER TABLE bot_sessions ADD COLUMN pending_token_account TEXT DEFAULT ''"
        )


def _migration_12_token_auto_refresh(c: sqlite3.Connection) -> None:
    if _table_exists(c, "accounts"):
        if not _column_exists(c, "accounts", "token_exp_at"):
            c.execute("ALTER TABLE accounts ADD COLUMN token_exp_at REAL")
        if not _column_exists(c, "accounts", "last_token_refresh_at"):
            c.execute("ALTER TABLE accounts ADD COLUMN last_token_refresh_at REAL")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS account_secrets (
            account_name TEXT PRIMARY KEY,
            login_enc TEXT NOT NULL DEFAULT '',
            updated_at REAL DEFAULT (strftime('%s','now'))
        )
        """
    )


MIGRATIONS: list[tuple[int, MigrationFn]] = [
    (1, _migration_1_indexes),
    (2, _migration_2_persistence_tables),
    (3, _migration_3_token_enc),
    (4, _migration_4_snapshot_indexes),
    (5, _migration_5_plaintext_tokens),
    (6, _migration_6_main_account),
    (7, _migration_7_account_missions),
    (8, _migration_8_easy_guide),
    (9, _migration_9_reply_keyboard_pref),
    (10, _migration_10_dashboard_pin),
    (11, _migration_11_pending_token_account),
    (12, _migration_12_token_auto_refresh),
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
