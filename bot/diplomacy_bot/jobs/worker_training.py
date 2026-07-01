"""Worker training sidecar — telegram'dan bağımsız saatlik antrenman."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

_STATE_KEY = "training_watch_last_attack"
_DEFAULT_MIN_INTERVAL_SEC = 55 * 60


def _load_last_attacks() -> dict[str, float]:
    from diplomacy_bot.health_state import load_health_state

    return dict(load_health_state().get(_STATE_KEY) or {})


def _save_attack_ts(account_name: str) -> None:
    from diplomacy_bot.health_state import load_health_state, save_health_state

    state = load_health_state()
    bucket = dict(state.get(_STATE_KEY) or {})
    bucket[account_name.strip().lower()] = time.time()
    state[_STATE_KEY] = bucket
    save_health_state(state)


def _recently_attacked(name: str, bucket: dict[str, float], min_interval_sec: float) -> bool:
    last = float(bucket.get(name.strip().lower()) or 0)
    return last > 0 and time.time() - last < min_interval_sec


def run_training_tick(*, min_interval_sec: float = _DEFAULT_MIN_INTERVAL_SEC) -> tuple[int, int]:
    """Aktif autofarm hesaplarda training hazırsa saldır. Dönüş: (ok, checked)."""
    from diplomacy_bot.account_config import get_config, normalize_role
    from diplomacy_bot.account_runtime import account_context
    from diplomacy_bot.modules import training
    from diplomacy_bot.store import list_accounts, log_action

    last_attacks = _load_last_attacks()
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
        except Exception as e:
            log.debug("worker_training %s: %s", name, e)
    if checked:
        log.info("worker: training %s/%s attack ok", ok, checked)
    return ok, checked
