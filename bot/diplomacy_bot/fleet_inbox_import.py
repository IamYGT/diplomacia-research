"""Filo inbox import — headless bağlama (job + callback ortak)."""

from __future__ import annotations

import logging

from .connect_core import connect_core
from .fleet_command import FleetBatchResult, FleetOpResult

log = logging.getLogger(__name__)


def format_inbox_import_footer(telegram_user_id: int, batch: FleetBatchResult) -> str:
    """Boş inbox'ta dosya yolu ipucu; doluysa standart next steps."""
    from .fleet_status import format_next_steps_footer

    if batch.total == 1 and batch.results and not batch.results[0].ok:
        msg = batch.results[0].message.lower()
        if "boş" in msg or "inbox" in msg:
            return (
                f"\n<i>Token yapıştır veya "
                f"<code>data/token_inbox/u{telegram_user_id}_01.jwt</code> bırak, "
                f"sonra tekrar <code>/fleetinbox</code></i>"
            )
    return format_next_steps_footer(telegram_user_id)


def connect_account_sync(name: str, token: str, *, telegram_user_id: int):
    """connect_core kısayolu."""
    return connect_core(name, token, telegram_user_id=telegram_user_id).account


def import_inbox_for_uid(telegram_user_id: int) -> FleetBatchResult:
    """Inbox'taki u{uid}_* tokenlarını headless bağla."""
    from .token_watch import list_inbox_import_candidates

    batch = FleetBatchResult()
    candidates = list_inbox_import_candidates(telegram_user_id)
    if not candidates:
        batch.add(FleetOpResult("-", False, "inbox boş"))
        return batch
    for name, tok in candidates:
        try:
            connect_account_sync(name, tok, telegram_user_id=telegram_user_id)
            from .token_watch import consume_inbox_for_account

            consume_inbox_for_account(name)
            batch.add(FleetOpResult(name, True, "bağlandı → DB"))
            log.info("fleet_inbox_import connected uid=%s name=%s", telegram_user_id, name)
        except Exception as e:
            batch.add(FleetOpResult(name, False, str(e)[:80]))
    return batch
