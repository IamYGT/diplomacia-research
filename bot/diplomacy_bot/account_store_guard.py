"""store.add_account / remove_account — legacy uid=0 claim koruması (store.py patch)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _guard_add_account(
    name: str,
    token: str,
    player_id: str = "",
    username: str = "",
    proxy_id: str = "direct",
    proxy_url: str = "",
    *,
    telegram_user_id: int = 0,
):
    from .auth import can_claim_orphan_account
    from .store import get_account

    existing = get_account(name.strip().lower())
    if existing and existing.telegram_user_id == 0 and telegram_user_id > 0:
        if not can_claim_orphan_account(name, telegram_user_id):
            raise ValueError(
                "Bu hesap adı legacy/atanmamış — farklı isim kullan "
                f"(ör. /add veya otomatik u{telegram_user_id}_isim)."
            )
    return _ORIG_ADD(
        name,
        token,
        player_id,
        username,
        proxy_id,
        proxy_url,
        telegram_user_id=telegram_user_id,
    )


def _guard_remove_account(name: str, *, telegram_user_id: int | None = None) -> bool:
    from .auth import is_admin
    from .store import get_account

    if telegram_user_id is not None:
        acc = get_account(name.strip().lower())
        if not acc:
            return False
        if acc.telegram_user_id != telegram_user_id:
            if not (acc.telegram_user_id == 0 and is_admin(telegram_user_id)):
                return False
    return _ORIG_REMOVE(name, telegram_user_id=telegram_user_id)


_ORIG_ADD = None
_ORIG_REMOVE = None


def install_store_guard_hooks() -> None:
    global _ORIG_ADD, _ORIG_REMOVE
    from . import store

    if getattr(store, "_account_guard_installed", False):
        return

    _ORIG_ADD = store.add_account
    _ORIG_REMOVE = store.remove_account
    store.add_account = _guard_add_account  # type: ignore[assignment]
    store.remove_account = _guard_remove_account  # type: ignore[assignment]
    store._account_guard_installed = True
    log.info("store add/remove legacy guard kuruldu")
