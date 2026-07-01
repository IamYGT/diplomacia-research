"""Inbox watch — yeni token gelince otomatik import + autopilot."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

from .config import FLEET_INBOX_AUTO_SETUP
from .inbox_processed_state import is_inbox_processed, mark_inbox_processed

log = logging.getLogger(__name__)


def _candidate_key(uid: int, name: str) -> str:
    return f"{uid}:{name.strip().lower()}"


def run_auto_inbox_setup_for_uid(telegram_user_id: int):
    """Import + autopilot — kalıcı state ile yeni aday varsa çalıştır."""
    from .fleet_mission_service import start_fleet_autopilot_for_uid
    from .token_watch import list_inbox_import_candidates

    candidates = list_inbox_import_candidates(telegram_user_id)
    fresh = [
        (n, t)
        for n, t in candidates
        if not is_inbox_processed(_candidate_key(telegram_user_id, n))
    ]
    if not fresh:
        return None

    result = start_fleet_autopilot_for_uid(telegram_user_id)
    from .fleet_inbox_import import successful_inbox_processed_keys

    keys = successful_inbox_processed_keys(telegram_user_id, result.inbox, [n for n, _ in fresh])
    if keys:
        mark_inbox_processed(keys)
    return result


async def fleet_inbox_watch_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """~300sn — inbox'ta yeni u{uid}_* token varsa import (+ opsiyonel AOD)."""
    from .token_watch import list_inbox_operator_uids

    if not FLEET_INBOX_AUTO_SETUP:
        return

    for uid in list_inbox_operator_uids():
        try:

            def _run(u: int = uid):
                return run_auto_inbox_setup_for_uid(u)

            result = await asyncio.to_thread(_run)
            if not result or not context.bot:
                continue
            from .fleet_region_mission_ui import format_autopilot_html

            text = format_autopilot_html(result)
            await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            log.info("fleet_inbox_watch autopilot uid=%s ok=%s", uid, result.inbox.ok)
        except Exception as e:
            log.warning("fleet_inbox_watch uid=%s: %s", uid, e)
