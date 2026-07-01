"""Inbox işlenen adaylar — PM2 restart sonrası kalıcı state."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .config import DATA_DIR

log = logging.getLogger(__name__)

_STATE_PATH = DATA_DIR / "inbox_processed.json"


def _load_raw() -> dict:
    if not _STATE_PATH.exists():
        return {"keys": []}
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("keys"), list):
            return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("inbox_processed load: %s", e)
    return {"keys": []}


def _save_raw(keys: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"keys": sorted(keys)}, ensure_ascii=False, indent=2)
    tmp = _STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, _STATE_PATH)


def load_processed_keys() -> set[str]:
    return set(str(k) for k in _load_raw().get("keys") or [])


def is_inbox_processed(key: str) -> bool:
    return key in load_processed_keys()


def mark_inbox_processed(keys: set[str] | list[str]) -> None:
    merged = load_processed_keys() | {str(k) for k in keys}
    _save_raw(merged)


def clear_inbox_processed_for_uid(telegram_user_id: int) -> None:
    """Test / manuel reset — uid prefix'li kayıtları sil."""
    prefix = f"{telegram_user_id}:"
    kept = {k for k in load_processed_keys() if not k.startswith(prefix)}
    _save_raw(kept)
