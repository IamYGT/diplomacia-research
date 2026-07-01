"""Hesap modeli ve satır dönüşümü."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

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


def token_from_row(row: sqlite3.Row) -> str:
    keys = row.keys()
    plain = str(row["token"] or "").strip()
    if plain == _TOKEN_SENTINEL or (not plain.startswith("eyJ") and "token_enc" in keys):
        enc = str(row["token_enc"] or "").strip()
        if enc:
            try:
                from ...token_crypto import decrypt_token

                return decrypt_token(enc) or plain
            except Exception:
                pass
    return plain if plain != _TOKEN_SENTINEL else ""


def row_to_account(row: sqlite3.Row) -> Account:
    keys = row.keys()
    return Account(
        id=row["id"],
        name=row["name"],
        token=token_from_row(row),
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
