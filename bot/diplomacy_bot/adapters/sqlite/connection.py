"""SQLite bağlantı fabrikası."""

from __future__ import annotations

import sqlite3


def open_connection() -> sqlite3.Connection:
    import importlib

    store = importlib.import_module("diplomacy_bot.store")
    db_path = store.DB_PATH
    data_dir = store.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=5000")
    return c
