"""Telegram kullanıcı erişimi ve hesap sahipliği."""

from __future__ import annotations

from .config import BOT_PUBLIC, TELEGRAM_ADMIN_IDS
from .store import Account, list_accounts, list_accounts_for_user


def is_admin(telegram_user_id: int) -> bool:
    return telegram_user_id in TELEGRAM_ADMIN_IDS


def bot_allows_user(telegram_user_id: int) -> bool:
    if BOT_PUBLIC:
        return True
    return is_admin(telegram_user_id)


def can_access_account(acc: Account, telegram_user_id: int) -> bool:
    if is_admin(telegram_user_id):
        return True
    if acc.telegram_user_id == 0:
        return False
    return acc.telegram_user_id == telegram_user_id


def scoped_list_accounts(telegram_user_id: int) -> list[Account]:
    """Operatörün kendi hesapları — admin başka kullanıcı hesabını görmez."""
    return list_accounts_for_user(telegram_user_id)


def admin_list_all_accounts(telegram_user_id: int) -> list[Account]:
    """Yalnızca admin — tüm DB hesapları (debug)."""
    if is_admin(telegram_user_id):
        return list_accounts()
    return list_accounts_for_user(telegram_user_id)


def resolve_account(name: str, telegram_user_id: int) -> Account | None:
    from .store import get_account

    acc = get_account(name)
    if not acc:
        return None
    if can_access_account(acc, telegram_user_id):
        return acc
    return None


def default_account_name(telegram_user_id: int, alias: str = "") -> str:
    alias = alias.strip().lower().replace(" ", "_")[:24]
    if alias:
        return f"u{telegram_user_id}_{alias}"
    return f"u{telegram_user_id}"


def account_name_for_user(name: str, telegram_user_id: int) -> bool:
    """Hesap adı bu Telegram kullanıcısının u{uid} ad alanında mı."""
    n = name.strip().lower()
    prefix = f"u{telegram_user_id}"
    return n == prefix or n.startswith(f"{prefix}_")


def can_claim_orphan_account(name: str, telegram_user_id: int) -> bool:
    """telegram_user_id=0 legacy satırı — yalnızca admin veya u{uid}_* sahibi claim edebilir."""
    if is_admin(telegram_user_id):
        return True
    return account_name_for_user(name, telegram_user_id)
