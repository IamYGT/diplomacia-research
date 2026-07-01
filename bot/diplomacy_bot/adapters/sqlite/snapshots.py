"""game_snapshots tablosu."""

from __future__ import annotations

import json
import sqlite3
import time

from .connection import open_connection


def save_game_snapshot(account_name: str, payload: dict, *, ttl_sec: float) -> None:
    now = time.time()
    name = account_name.strip().lower()
    with open_connection() as c:
        c.execute(
            """
            INSERT INTO game_snapshots (account_name, payload_json, fetched_at, stale_after)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                payload_json=excluded.payload_json,
                fetched_at=excluded.fetched_at,
                stale_after=excluded.stale_after
            """,
            (name, json.dumps(payload, ensure_ascii=False), now, now + ttl_sec),
        )


def get_game_snapshot(account_name: str, *, max_age_sec: float | None = None) -> dict | None:
    name = account_name.strip().lower()
    try:
        with open_connection() as c:
            row = c.execute(
                "SELECT payload_json, fetched_at, stale_after FROM game_snapshots WHERE account_name=?",
                (name,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    fetched = float(row["fetched_at"])
    if max_age_sec is not None and time.time() - fetched > max_age_sec:
        return None
    try:
        return json.loads(row["payload_json"])
    except json.JSONDecodeError:
        return None


def game_snapshot_age_sec(account_name: str) -> float | None:
    name = account_name.strip().lower()
    try:
        with open_connection() as c:
            row = c.execute(
                "SELECT fetched_at FROM game_snapshots WHERE account_name=?",
                (name,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return time.time() - float(row["fetched_at"])


def delete_game_snapshot(account_name: str | None = None) -> None:
    try:
        with open_connection() as c:
            if account_name:
                c.execute(
                    "DELETE FROM game_snapshots WHERE account_name=?",
                    (account_name.strip().lower(),),
                )
            else:
                c.execute("DELETE FROM game_snapshots")
    except sqlite3.OperationalError:
        return
