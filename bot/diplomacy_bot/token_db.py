"""Token kalıcılığı — tek kaynak: SQLite accounts.token (+ account_secrets).

Runtime'da JWT okuma/yazma yalnızca bu modül ve connect_core üzerinden.
token_inbox/ = geçici import kuyruğu; DB'ye yazılınca dosya silinir.
"""

from __future__ import annotations

import logging

from .connect_core import ConnectCoreResult, connect_core
from .store import Account, get_account

log = logging.getLogger(__name__)


def get_stored_token(account_name: str) -> str:
    """Çalışma anı token — yalnızca DB."""
    acc = get_account(account_name)
    if not acc:
        return ""
    return (acc.token or "").strip()


def persist_account_token(
    name: str,
    token: str,
    *,
    telegram_user_id: int,
    consume_inbox: bool = True,
) -> ConnectCoreResult:
    """Token doğrula → DB'ye yaz → (opsiyonel) inbox dosyasını kaldır."""
    result = connect_core(name, token, telegram_user_id=telegram_user_id)
    if consume_inbox:
        from .token_watch import consume_inbox_for_account

        if consume_inbox_for_account(result.account.name):
            log.info("token_db: inbox consumed for %s", result.account.name)
    return result


def account_token_summary(acc: Account) -> dict:
    """DB token meta — dosya/inbox yok."""
    from .jwt_meta import expires_in_sec, format_expiry_human, is_expired
    from .token_meta_store import get_token_exp_at

    tok = (acc.token or "").strip()
    exp_db = get_token_exp_at(acc.name)
    return {
        "name": acc.name,
        "has_token": tok.startswith("eyJ"),
        "source": "db",
        "expired": is_expired(tok) if tok else True,
        "expires_in_sec": expires_in_sec(tok),
        "exp_human": format_expiry_human(tok) if tok else "—",
        "token_exp_at": exp_db,
    }
