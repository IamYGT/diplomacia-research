from __future__ import annotations

import re
from typing import Any

BLOCKED_PREFIXES = (
    "/auth/",
    "/mod/",
    "/moderation/",
    "/upload/",
)

CONFIRM_PREFIXES = (
    "/transfer/send",
    "/wars/declare",
    "/wars/",
    "/market/",
    "/factories/close",
    "/factories/fire",
    "/players/diamonds/",
    "/diplomacy/embargo/",
)

MAX_TRANSFER_AUTO = 50_000


def classify_action(method: str, path: str, body: dict | None) -> str:
    """safe | confirm | blocked"""
    p = path.split("?")[0].lower()
    for pref in BLOCKED_PREFIXES:
        if p.startswith(pref):
            return "blocked"
    for pref in CONFIRM_PREFIXES:
        if p.startswith(pref) or pref.rstrip("/") in p:
            if p.startswith("/transfer/send") and body:
                amt = int(body.get("amount") or 0)
                if amt <= MAX_TRANSFER_AUTO:
                    return "confirm"
            return "confirm"
    return "safe"


def action_summary(method: str, path: str, body: Any) -> str:
    b = ""
    if body:
        b = f" body={str(body)[:200]}"
    return f"{method} {path}{b}"


def sanitize_path(path: str) -> str:
    return re.sub(r"[^\w/\-\{\}\?=&%.]", "", path)[:200]
