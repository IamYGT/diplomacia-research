"""Worker training sidecar — telegram'dan bağımsız saatlik antrenman."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

_STATE_KEY = "training_watch_last_attack"
_NEXT_KEY = "training_watch_next_attempt"
_DEFAULT_MIN_INTERVAL_SEC = 55 * 60
_NO_WAR_RETRY_SEC = 10 * 60
_ATTACK_ERROR_RETRY_SEC = 5 * 60


def _load_last_attacks() -> dict[str, float]:
    from diplomacy_bot.health_state import load_health_state

    return dict(load_health_state().get(_STATE_KEY) or {})


def _load_next_attempts() -> dict[str, float]:
    from diplomacy_bot.health_state import load_health_state

    return dict(load_health_state().get(_NEXT_KEY) or {})


def _save_attack_ts(account_name: str) -> None:
    from diplomacy_bot.health_state import load_health_state, save_health_state

    state = load_health_state()
    bucket = dict(state.get(_STATE_KEY) or {})
    bucket[account_name.strip().lower()] = time.time()
    state[_STATE_KEY] = bucket
    save_health_state(state)


def _save_next_attempt_ts(account_name: str, when_ts: float) -> None:
    from diplomacy_bot.health_state import load_health_state, save_health_state

    state = load_health_state()
    bucket = dict(state.get(_NEXT_KEY) or {})
    bucket[account_name.strip().lower()] = when_ts
    state[_NEXT_KEY] = bucket
    save_health_state(state)


def _recently_attacked(name: str, bucket: dict[str, float], min_interval_sec: float) -> bool:
    last = float(bucket.get(name.strip().lower()) or 0)
    return last > 0 and time.time() - last < min_interval_sec


def _next_attempt_not_due(name: str, bucket: dict[str, float]) -> bool:
    return float(bucket.get(name.strip().lower()) or 0) > time.time()


def _schedule_retry_from_result(name: str, result: dict | None, min_interval_sec: float) -> None:
    if not result:
        return
    skipped = result.get("skipped")
    if skipped == "free_attack_cooldown":
        wait_ms = int(result.get("ms") or 300_000)
        _save_next_attempt_ts(name, time.time() + max(60.0, wait_ms / 1000.0))
    elif skipped in ("no_training_war", "no_training_war_id"):
        _save_next_attempt_ts(name, time.time() + min(_NO_WAR_RETRY_SEC, min_interval_sec))
    elif skipped == "training_attack_error":
        _save_next_attempt_ts(name, time.time() + min(_ATTACK_ERROR_RETRY_SEC, min_interval_sec))


def run_training_tick(*, min_interval_sec: float = _DEFAULT_MIN_INTERVAL_SEC) -> tuple[int, int]:
    """Aktif autofarm hesaplarda training hazırsa saldır. Dönüş: (ok, checked)."""
    from diplomacy_bot.account_config import get_config, normalize_role
    from diplomacy_bot.account_runtime import account_context
    from diplomacy_bot.modules import training
    from diplomacy_bot.store import list_accounts, log_action

    last_attacks = _load_last_attacks()
    next_attempts = _load_next_attempts()
    ok = 0
    checked = 0
    for acc in list_accounts():
        name = acc.name.strip().lower()
        if not acc.autofarm or acc.status != "active":
            continue
        cfg = get_config(name)
        if not cfg.training_enabled or normalize_role(cfg.role) not in ("farm", "war", "hybrid"):
            continue
        if _recently_attacked(name, last_attacks, min_interval_sec):
            continue
        if _next_attempt_not_due(name, next_attempts):
            continue
        checked += 1
        try:
            with account_context(acc, rotate_egress=True):
                result = training.try_free_attack(acc.token, cfg)
            if result and result.get("ok"):
                _save_attack_ts(name)
                log_action(
                    "training_attack",
                    account_name=name,
                    telegram_user_id=acc.telegram_user_id or 0,
                    result="worker_training",
                    success=True,
                )
                ok += 1
            else:
                _schedule_retry_from_result(name, result, min_interval_sec)
                skipped = (result or {}).get("skipped") or "no_result"
                log_action(
                    "training_skip",
                    account_name=name,
                    telegram_user_id=acc.telegram_user_id or 0,
                    result=str(skipped),
                    success=False,
                )
        except Exception as e:
            log.debug("worker_training %s: %s", name, e)
            _save_next_attempt_ts(name, time.time() + min(_ATTACK_ERROR_RETRY_SEC, min_interval_sec))
            log_action(
                "training_skip",
                account_name=name,
                telegram_user_id=acc.telegram_user_id or 0,
                result="training_exception",
                success=False,
            )
    if checked:
        log.info("worker: training %s/%s attack ok", ok, checked)
    return ok, checked
