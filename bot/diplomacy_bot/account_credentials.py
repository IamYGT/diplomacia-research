"""Hesap giriş bilgisi — Fernet ile şifreli (otomatik login için)."""

from __future__ import annotations

import json
import time

from .token_crypto import _fernet


def _encrypt_blob(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def _decrypt_blob(stored: str) -> str:
    if not stored:
        return ""
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def _conn():
    from .store import _conn as store_conn

    return store_conn()


def init_secrets_table() -> None:
    from .db_migrate import run_migrations

    with _conn() as c:
        run_migrations(c)


def save_login(account_name: str, email: str, password: str) -> None:
    init_secrets_table()
    name = account_name.strip().lower()
    payload = json.dumps({"email": email.strip(), "password": password})
    enc = _encrypt_blob(payload)
    now = time.time()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO account_secrets (account_name, login_enc, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                login_enc=excluded.login_enc,
                updated_at=excluded.updated_at
            """,
            (name, enc, now),
        )


def load_login(account_name: str) -> tuple[str, str] | None:
    init_secrets_table()
    name = account_name.strip().lower()
    with _conn() as c:
        row = c.execute(
            "SELECT login_enc FROM account_secrets WHERE account_name=?",
            (name,),
        ).fetchone()
    if not row or not row["login_enc"]:
        return None
    raw = _decrypt_blob(str(row["login_enc"]))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    email = str(data.get("email") or "").strip()
    password = str(data.get("password") or "")
    if not email or not password:
        return None
    return email, password


def has_login(account_name: str) -> bool:
    return load_login(account_name) is not None


def clear_login(account_name: str) -> bool:
    init_secrets_table()
    name = account_name.strip().lower()
    with _conn() as c:
        cur = c.execute("DELETE FROM account_secrets WHERE account_name=?", (name,))
        return cur.rowcount > 0
