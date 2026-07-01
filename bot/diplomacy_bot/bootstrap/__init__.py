"""Uygulama bootstrap — hook'lar telegram run() öncesi kurulur (M0)."""

from __future__ import annotations

import logging

from .domain_registry import install_domain_hooks
from .registry import install_explicit_hooks

log = logging.getLogger(__name__)

_INSTALLED = False

__all__ = ["install_bootstrap", "install_explicit_hooks", "install_domain_hooks"]


def install_bootstrap() -> None:
    """DB hazırlığı + runtime wiring — telegram_app.run() öncesi ZORUNLU."""
    global _INSTALLED
    if _INSTALLED:
        return

    from diplomacy_bot.store import init_db

    init_db()

    import diplomacy_bot.dashboard_readiness  # noqa: F401

    install_explicit_hooks()
    install_domain_hooks()

    _finalize_ui_bindings()
    _INSTALLED = True
    log.info("Bootstrap tamamlandı (M0)")


def _finalize_ui_bindings() -> None:
    from diplomacy_bot import telegram_ui as ui
    from diplomacy_bot.account_scope import rebootstrap_ui_consumers

    rebootstrap_ui_consumers(
        ui.format_accounts_html,
        ui.accounts_inline_markup,
    )
