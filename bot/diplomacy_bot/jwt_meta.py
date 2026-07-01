"""JWT süre meta — exp/iat ve yenileme kararı."""

from __future__ import annotations

import time
from typing import Any

from .connect_intel import decode_jwt_payload


def token_exp_unix(token: str) -> float | None:
    claims = decode_jwt_payload(token)
    exp = claims.get("exp")
    if exp is None:
        return None
    try:
        return float(exp)
    except (TypeError, ValueError):
        return None


def token_iat_unix(token: str) -> float | None:
    claims = decode_jwt_payload(token)
    iat = claims.get("iat")
    if iat is None:
        return None
    try:
        return float(iat)
    except (TypeError, ValueError):
        return None


def token_lifetime_sec(token: str) -> float | None:
    exp = token_exp_unix(token)
    iat = token_iat_unix(token)
    if exp is None or iat is None:
        return None
    return max(0.0, exp - iat)


def expires_in_sec(token: str, *, now: float | None = None) -> float | None:
    exp = token_exp_unix(token)
    if exp is None:
        return None
    return exp - (now if now is not None else time.time())


def is_expired(token: str, *, now: float | None = None) -> bool:
    left = expires_in_sec(token, now=now)
    if left is None:
        return False
    return left <= 0


def is_expiring_soon(token: str, *, lead_sec: float, now: float | None = None) -> bool:
    """Süre dolmadan lead_sec içindeyse True."""
    left = expires_in_sec(token, now=now)
    if left is None:
        return False
    return left <= lead_sec


def player_id_from_token(token: str) -> str:
    claims = decode_jwt_payload(token)
    return str(claims.get("id") or claims.get("player_id") or "")


def format_expiry_human(token: str, *, now: float | None = None) -> str:
    left = expires_in_sec(token, now=now)
    if left is None:
        return "bilinmiyor"
    if left <= 0:
        return "dolmuş"
    hours = int(left // 3600)
    if hours >= 48:
        days = hours // 24
        return f"{days} gün"
    if hours >= 1:
        return f"{hours} saat"
    return f"{int(left // 60)} dk"
