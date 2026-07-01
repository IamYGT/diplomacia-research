"""Oturum varsayılan hesabı — main_account ↔ active_account (telegram_helpers patch)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_default_account_main_hook() -> None:
    from . import telegram_helpers as th

    if getattr(th, "_main_account_default_installed", False):
        return

    _orig = th._default_account

    def _default_account_with_main(context, uid: int) -> str | None:
        name = _orig(context, uid)
        if name:
            return name
        from .auth import resolve_account
        from .store import get_session

        sess = get_session(uid)
        if not sess:
            return None
        main = (sess.get("main_account") or "").strip().lower()
        if main and resolve_account(main, uid):
            th._set_default_account(context, uid, main)
            return main
        return None

    th._default_account = _default_account_with_main
    th._main_account_default_installed = True
    log.info("default_account main_account fallback kuruldu")
