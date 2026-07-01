"""Inbox watch — yeni token gelince otomatik import + AOD kurulum."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

from .config import FLEET_INBOX_AUTO_SETUP
from .fleet_command import format_batch_html
from .fleet_help import format_fleet_coach_hint
from .fleet_inbox_import import import_inbox_for_uid
from .fleet_residence import run_aod_setup
from .fleet_status import format_post_aod_footer
from .inbox_processed_state import is_inbox_processed, mark_inbox_processed

log = logging.getLogger(__name__)


def _candidate_key(uid: int, name: str) -> str:
    return f"{uid}:{name.strip().lower()}"


def format_auto_inbox_setup_html(uid: int, import_batch, aod_steps: dict) -> str:
    """Otomatik inbox+AOD özeti."""
    parts = [
        format_batch_html("📥 Otomatik inbox import", import_batch),
        "",
        "<b>🇦🇴 AOD kurulum</b>",
    ]
    for step, batch in aod_steps.items():
        parts.append(f"• {step}: {batch.ok}/{batch.total} OK")
    parts.append(format_post_aod_footer())
    parts.append(f"\n<i>{format_fleet_coach_hint()}</i>")
    return "\n".join(parts)


def run_auto_inbox_setup_for_uid(telegram_user_id: int) -> tuple | None:
    """Import + AOD — kalıcı state ile yeni aday varsa çalıştır."""
    from .token_watch import list_inbox_import_candidates

    candidates = list_inbox_import_candidates(telegram_user_id)
    fresh = [
        (n, t)
        for n, t in candidates
        if not is_inbox_processed(_candidate_key(telegram_user_id, n))
    ]
    if not fresh:
        return None

    import_batch = import_inbox_for_uid(telegram_user_id)
    mark_inbox_processed({_candidate_key(telegram_user_id, n) for n, _ in fresh})

    aod_steps = run_aod_setup(telegram_user_id)
    return import_batch, aod_steps


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
            import_batch, aod_steps = result
            text = format_auto_inbox_setup_html(uid, import_batch, aod_steps)
            await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            log.info("fleet_inbox_watch auto setup uid=%s ok=%s", uid, import_batch.ok)
        except Exception as e:
            log.warning("fleet_inbox_watch uid=%s: %s", uid, e)
