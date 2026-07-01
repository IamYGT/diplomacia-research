"""Worker inbox setup — token_inbox'tan otomatik import + AOD."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _candidate_key(uid: int, name: str) -> str:
    return f"{uid}:{name.strip().lower()}"


def run_worker_inbox_setup_once() -> tuple[int, int]:
    """Yeni inbox adaylarını import eder ve AOD zincirini çalıştırır.

    Dönüş: (işlenen operator uid sayısı, başarılı import sayısı).
    """
    from diplomacy_bot.fleet_inbox_import import import_inbox_for_uid
    from diplomacy_bot.fleet_residence import run_aod_setup
    from diplomacy_bot.inbox_processed_state import is_inbox_processed, mark_inbox_processed
    from diplomacy_bot.token_watch import list_inbox_import_candidates, list_inbox_operator_uids

    uids = 0
    imported = 0
    for uid in list_inbox_operator_uids():
        candidates = list_inbox_import_candidates(uid)
        fresh = [(n, t) for n, t in candidates if not is_inbox_processed(_candidate_key(uid, n))]
        if not fresh:
            continue
        batch = import_inbox_for_uid(uid)
        mark_inbox_processed({_candidate_key(uid, n) for n, _ in fresh})
        run_aod_setup(uid)
        uids += 1
        imported += batch.ok
        log.info("worker inbox setup uid=%s import=%s/%s", uid, batch.ok, batch.total)
    return uids, imported
