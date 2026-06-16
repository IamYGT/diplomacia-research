from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable

from .config import DB_PATH, DATA_DIR, LEGACY_AUTH, TELEGRAM_ADMIN_IDS
from .db_migrate import run_migrations

_TOKEN_SENTINEL = "__enc__"


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
    telegram_user_id: int = 0
    runtime_state: str = "idle"


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=5000")
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
                created_at REAL DEFAULT (strftime('%s','now')),
                telegram_user_id INTEGER DEFAULT 0
            )
            """
        )
        _migrate_legacy_columns(c)
        run_migrations(c)
        _migrate_legacy_owners(c)


def _migrate_legacy_columns(c: sqlite3.Connection) -> None:
    """Eski kurulumlar — migration öncesi kolon ekleme."""
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


def _legacy_owner_id() -> int:
    if TELEGRAM_ADMIN_IDS:
        return next(iter(TELEGRAM_ADMIN_IDS))
    return 0


def _token_from_row(row: sqlite3.Row) -> str:
    keys = row.keys()
    plain = str(row["token"] or "").strip()
    if plain == _TOKEN_SENTINEL or (not plain.startswith("eyJ") and "token_enc" in keys):
        enc = str(row["token_enc"] or "").strip()
        if enc:
            try:
                from .token_crypto import decrypt_token

                return decrypt_token(enc) or plain
            except Exception:
                pass
    return plain if plain != _TOKEN_SENTINEL else ""


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
        telegram_user_id=_legacy_owner_id(),
    )


def find_account_by_player_id(player_id: str) -> Account | None:
    if not player_id:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM accounts WHERE player_id=? LIMIT 1",
            (player_id.strip(),),
        ).fetchone()
    return _row_to_account(row) if row else None


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
    with _conn() as c:
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
    with _conn() as c:
        c.execute("DELETE FROM game_snapshots WHERE account_name=?", (name,))
        cur = c.execute("DELETE FROM accounts WHERE name=?", (name,))
        return cur.rowcount > 0


def list_accounts() -> list[Account]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    return [_row_to_account(r) for r in rows]


def list_accounts_for_user(telegram_user_id: int) -> list[Account]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM accounts WHERE telegram_user_id=? ORDER BY name",
            (telegram_user_id,),
        ).fetchall()
    return [_row_to_account(r) for r in rows]


def count_accounts_for_user(telegram_user_id: int) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM accounts WHERE telegram_user_id=?",
            (telegram_user_id,),
        ).fetchone()
    return int(row["n"]) if row else 0


def get_account(name: str) -> Account | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM accounts WHERE name=?", (name.strip().lower(),)).fetchone()
    return _row_to_account(row) if row else None


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


def set_runtime_state(name: str, state: str) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE accounts SET runtime_state=? WHERE name=?",
            (state.strip().lower()[:32], name.strip().lower()),
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


# --- game_snapshots ---


def save_game_snapshot(account_name: str, payload: dict, *, ttl_sec: float) -> None:
    now = time.time()
    name = account_name.strip().lower()
    with _conn() as c:
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
        with _conn() as c:
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
        with _conn() as c:
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
        with _conn() as c:
            if account_name:
                c.execute(
                    "DELETE FROM game_snapshots WHERE account_name=?",
                    (account_name.strip().lower(),),
                )
            else:
                c.execute("DELETE FROM game_snapshots")
    except sqlite3.OperationalError:
        return


# --- action_log ---


def log_action(
    action: str,
    *,
    account_name: str = "",
    telegram_user_id: int = 0,
    result: str = "",
    success: bool = True,
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO action_log (account_name, telegram_user_id, action, result, success)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                account_name.strip().lower() if account_name else "",
                telegram_user_id,
                action[:64],
                (result or "")[:500],
                1 if success else 0,
            ),
        )


def recent_actions(account_name: str, limit: int = 10) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT action, result, success, created_at, telegram_user_id
            FROM action_log
            WHERE account_name=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (account_name.strip().lower(), limit),
        ).fetchall()
    return [dict(r) for r in rows]


# --- bot_sessions ---


def get_session(telegram_user_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM bot_sessions WHERE telegram_user_id=?",
            (telegram_user_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_session(
    telegram_user_id: int,
    *,
    active_account: str | None = None,
    last_menu: str | None = None,
    pending_connect: bool | None = None,
) -> None:
    now = time.time()
    existing = get_session(telegram_user_id) or {}
    acc = active_account if active_account is not None else existing.get("active_account")
    menu = last_menu if last_menu is not None else existing.get("last_menu", "")
    pending = (
        int(pending_connect)
        if pending_connect is not None
        else int(existing.get("pending_connect") or 0)
    )
    with _conn() as c:
        c.execute(
            """
            INSERT INTO bot_sessions (telegram_user_id, active_account, last_menu, pending_connect, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                active_account=excluded.active_account,
                last_menu=excluded.last_menu,
                pending_connect=excluded.pending_connect,
                updated_at=excluded.updated_at
            """,
            (telegram_user_id, acc, menu or "", pending, now),
        )


def clear_session_pending(telegram_user_id: int) -> None:
    upsert_session(telegram_user_id, pending_connect=False)


def _row_to_account(row: sqlite3.Row) -> Account:
    keys = row.keys()
    return Account(
        id=row["id"],
        name=row["name"],
        token=_token_from_row(row),
        player_id=row["player_id"] or "",
        username=row["username"] or "",
        autofarm=bool(row["autofarm"]),
        last_farm_at=float(row["last_farm_at"] or 0),
        last_balance=int(row["last_balance"] or 0),
        proxy_id=str(row["proxy_id"] or "direct") if "proxy_id" in keys else "direct",
        proxy_url=str(row["proxy_url"] or "") if "proxy_url" in keys else "",
        status=str(row["status"] or "active") if "status" in keys else "active",
        telegram_user_id=int(row["telegram_user_id"] or 0) if "telegram_user_id" in keys else 0,
        runtime_state=str(row["runtime_state"] or "idle") if "runtime_state" in keys else "idle",
    )
