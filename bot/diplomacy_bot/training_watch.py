"""Antrenman savaşı — free_attack_available iken ek saldırı tetikle."""

from __future__ import annotations

import asyncio
import logging
import time

from telegram.ext import ContextTypes

from .account_config import get_config, normalize_role
from .modules.economy import get_auto_status
from .modules import training
from .store import list_accounts

log = logging.getLogger(__name__)

_STATE_PATH_KEY = "training_watch_last_attack"


def _load_state() -> dict[str, float]:
    from .health_state import load_health_state

    raw = load_health_state()
    return dict(raw.get(_STATE_PATH_KEY) or {})


def _save_attack_ts(account_name: str) -> None:
    from .health_state import load_health_state, save_health_state

    state = load_health_state()
    bucket = dict(state.get(_STATE_PATH_KEY) or {})
    bucket[account_name.strip().lower()] = time.time()
    state[_STATE_PATH_KEY] = bucket
    save_health_state(state)


def try_training_if_ready(account_name: str, token: str) -> dict | None:
    """CD hazırsa antrenman saldırısı — idempotent."""
    cfg = get_config(account_name)
    role = normalize_role(cfg.role)
    if not cfg.training_enabled or role not in ("farm", "war", "hybrid"):
        return None
    status = get_auto_status(token) or {}
    if not status.get("free_attack_available"):
        return None
    result = training.try_free_attack(token, cfg)
    if result and result.get("ok"):
        _save_attack_ts(account_name)
        log.info("training_watch attack ok acc=%s", account_name)
    return result


async def training_watch_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """~300sn — hazır antrenman saldırısı (autofarm tick'e ek)."""
    from .account_runtime import account_context

    for acc in list_accounts():
        if not acc.autofarm:
            continue
        try:

            def _run():
                with account_context(acc, rotate_egress=True):
                    r = try_training_if_ready(acc.name, acc.token)
                    if r and r.get("ok"):
                        from .store import log_action

                        log_action(
                            "training_attack",
                            account_name=acc.name,
                            telegram_user_id=acc.telegram_user_id or 0,
                            result="free_attack",
                            success=True,
                        )
                    return r

            await asyncio.to_thread(_run)
        except Exception as e:
            log.debug("training_watch %s: %s", acc.name, e)
