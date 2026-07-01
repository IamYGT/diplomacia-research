"""Diplomacia /auth/login — kayıtlı e-posta/şifre ile JWT al."""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import API_BASE
from .stealth_client import stealth_request

log = logging.getLogger(__name__)


def _extract_token_from_body(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("token", "access_token", "accessToken", "jwt"):
        val = data.get(key)
        if isinstance(val, str) and val.startswith("eyJ"):
            return val.strip()
    for nest in ("user", "player", "data"):
        sub = data.get(nest)
        if isinstance(sub, dict):
            t = _extract_token_from_body(sub)
            if t:
                return t
    return ""


def login_for_token(email: str, password: str) -> tuple[str | None, str]:
    """Başarılıysa (token, ""), değilse (None, hata_metni)."""
    body = {
        "email": email.strip(),
        "password": password,
        "device_fingerprint": "",
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; DiplomacyYGTBot/2.1)",
        "Origin": "https://diplomacia.com.tr",
        "Referer": "https://diplomacia.com.tr/",
    }
    try:
        st, raw = stealth_request(
            "POST",
            API_BASE + "/auth/login",
            headers=headers,
            data=json.dumps(body).encode(),
            delay=0,
        )
    except Exception as e:
        log.warning("login request failed: %s", e)
        return None, str(e)

    parsed: dict[str, Any] = {}
    if raw.strip().startswith("{"):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:200]}
    else:
        parsed = {"raw": raw[:200]}

    if st >= 400:
        err = (
            parsed.get("error")
            or parsed.get("message")
            or parsed.get("raw")
            or f"HTTP {st}"
        )
        return None, str(err)

    token = _extract_token_from_body(parsed)
    if not token:
        return None, "Yanıtta token bulunamadı (Turnstile gerekebilir)"
    return token, ""
