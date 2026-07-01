"""Token text helpers — Telegram bağımsız JWT çıkarma."""

from __future__ import annotations

import re


def extract_jwt_from_text(text: str) -> str | None:
    match = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", text or "")
    return match.group(0) if match else None
