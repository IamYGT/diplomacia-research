"""Hesap bağlama çekirdeği — interactive + headless ortak."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .store import Account


@dataclass
class ConnectCoreResult:
    account: Account
    profile: Any
    is_new: bool


def connect_core(name: str, token: str, *, telegram_user_id: int) -> ConnectCoreResult:
    """Token doğrula, DB'ye yaz — Telegram/UI yok."""
    from .account_pool import suggest_proxy
    from .account_runtime import account_context
    from .auth import resolve_account
    from .auto_defaults import apply_auto_defaults_for_new_account
    from .config import MAX_ACCOUNTS_PER_USER
    from .game_api import get_profile
    from .store import add_account, count_accounts_for_user, proxy_assignments
    from .token_meta_store import record_token_saved

    existing = resolve_account(name, telegram_user_id)
    if count_accounts_for_user(telegram_user_id) >= MAX_ACCOUNTS_PER_USER and not existing:
        raise ValueError(f"En fazla {MAX_ACCOUNTS_PER_USER} hesap")

    slot = suggest_proxy(proxy_assignments())
    with account_context(proxy_id=slot.id, proxy_url=slot.url or None):
        prof = get_profile(token)

    is_new = existing is None
    acc = add_account(
        name,
        token,
        prof.player_id,
        prof.username,
        slot.id,
        slot.url,
        telegram_user_id=telegram_user_id,
    )
    if is_new:
        apply_auto_defaults_for_new_account(acc.name)
    record_token_saved(acc.name, token)
    return ConnectCoreResult(account=acc, profile=prof, is_new=is_new)
