"""Birleşik health/watch state — pill CD + alert snapshot (tek dosya)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from .config import DATA_DIR

log = logging.getLogger(__name__)
_STATE_FILE = DATA_DIR / "health_watch_state.json"
_LEGACY_PILL_FILE = DATA_DIR / "pill_cd_state.json"


def load_health_state() -> dict[str, dict[str, Any]]:
    if _STATE_FILE.exists():
        try:
            raw = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception as e:
            log.warning("health_watch_state load: %s", e)
    if _LEGACY_PILL_FILE.exists():
        try:
            legacy = json.loads(_LEGACY_PILL_FILE.read_text(encoding="utf-8"))
            if isinstance(legacy, dict):
                migrated = {
                    k: {"pill_cooldown_ms": v.get("pill_cooldown_ms", 0), "ts": v.get("ts")}
                    for k, v in legacy.items()
                    if isinstance(v, dict)
                }
                save_health_state(migrated)
                return migrated
        except Exception:
            pass
    return {}


def save_health_state(state: dict[str, dict[str, Any]]) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception as e:
        log.warning("health_watch_state save: %s", e)


def account_row(state: dict, account_name: str) -> dict[str, Any]:
    return dict(state.get(account_name.strip().lower()) or {})


def update_account_row(state: dict, account_name: str, **fields: Any) -> None:
    name = account_name.strip().lower()
    row = dict(state.get(name) or {})
    row.update(fields)
    row["ts"] = time.time()
    state[name] = row
