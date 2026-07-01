"""M4 — runtime_install yerine explicit hook kaydı."""

from __future__ import annotations

import logging
from collections.abc import Callable

from .hooks.telegram_ptb_jobs import install_telegram_ptb_jobs
from .hooks.cmd_start_onboarding import install_cmd_start_onboarding
from .hooks.dashboard_coach import install_dashboard_coach
from .hooks.dashboard_flood import install_dashboard_flood
from .hooks.dashboard_release_badge import install_dashboard_release_badge
from .hooks.easy_callbacks import install_easy_callbacks
from .hooks.easy_mode_ui import install_easy_mode_ui
from .hooks.health_sync_ui import install_health_sync_ui
from .hooks.mission_account import install_mission_account_hooks
from .hooks.reply_keyboard_entries import install_reply_keyboard_entries
from .hooks.settings_easy import install_settings_easy
from .hooks.telegram_dispatch import install_telegram_dispatch
from .hooks.telegram_tabs import install_telegram_tabs
from .hooks.telegram_updates import install_telegram_updates
from .hooks.token_recovery import install_token_recovery

log = logging.getLogger(__name__)

_EXPLICIT_HOOKS: tuple[Callable[[], None], ...] = (
    install_easy_mode_ui,
    install_dashboard_release_badge,
    install_health_sync_ui,
    install_dashboard_flood,
    install_settings_easy,
    install_telegram_updates,
    install_telegram_ptb_jobs,
    install_telegram_tabs,
    install_token_recovery,
    install_telegram_dispatch,
    install_cmd_start_onboarding,
    install_reply_keyboard_entries,
    install_mission_account_hooks,
    install_easy_callbacks,
    install_dashboard_coach,
)
_INSTALLED = False


def install_explicit_hooks() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    for hook in _EXPLICIT_HOOKS:
        hook()
    _INSTALLED = True
    log.info("Explicit bootstrap hooks kuruldu (%s)", len(_EXPLICIT_HOOKS))
