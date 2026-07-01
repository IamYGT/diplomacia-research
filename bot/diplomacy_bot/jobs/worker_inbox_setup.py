"""Worker inbox setup — token_inbox'tan otomatik import + autopilot."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def run_worker_inbox_setup_once() -> tuple[int, int]:
    """Yeni inbox adaylarını import eder ve autopilot zincirini çalıştırır.

    Dönüş: (işlenen operator uid sayısı, başarılı import sayısı).
    """
    from diplomacy_bot.fleet_mission_service import start_fleet_autopilot_for_uid
    from diplomacy_bot.fleet_inbox_import import successful_inbox_processed_keys
    from diplomacy_bot.inbox_setup_lock import acquire_inbox_setup_lock
    from diplomacy_bot.inbox_processed_state import is_inbox_candidate_processed, mark_inbox_processed
    from diplomacy_bot.token_watch import list_inbox_import_candidates, list_inbox_operator_uids

    uids = 0
    imported = 0
    for uid in list_inbox_operator_uids():
        with acquire_inbox_setup_lock(uid) as locked:
            if not locked:
                continue
            candidates = list_inbox_import_candidates(uid)
            fresh = [(n, t) for n, t in candidates if not is_inbox_candidate_processed(uid, n, t)]
            if not fresh:
                continue
            result = start_fleet_autopilot_for_uid(uid)
            keys = successful_inbox_processed_keys(uid, result.inbox, fresh)
            if keys:
                mark_inbox_processed(keys)
            uids += 1
            imported += result.inbox.ok
            log.info("worker inbox autopilot uid=%s import=%s/%s", uid, result.inbox.ok, result.inbox.total)
    return uids, imported
