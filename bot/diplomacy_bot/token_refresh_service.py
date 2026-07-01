"""Token yenileme orkestrasyonu — inbox, legacy, API login."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .account_credentials import load_login
from .account_config import get_config
from .config import TOKEN_REFRESH_LEAD_SEC
from .jwt_meta import (
    expires_in_sec,
    format_expiry_human,
    is_expired,
    is_expiring_soon,
    player_id_from_token,
    token_exp_unix,
)
from .token_auto_login import login_for_token
from .token_meta_store import record_token_saved
from .token_watch import (
    pick_inbox_token,
    read_legacy_auth_token,
    scan_token_inbox,
    token_matches_account,
)

if TYPE_CHECKING:
    from .store import Account

log = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    account_name: str
    ok: bool
    source: str = ""
    message: str = ""


def should_refresh_account(acc: "Account", *, lead_sec: float | None = None) -> bool:
    cfg = get_config(acc.name)
    if not cfg.auto_token_refresh:
        return False
    lead = lead_sec if lead_sec is not None else float(TOKEN_REFRESH_LEAD_SEC)
    token = acc.token or ""
    if not token.startswith("eyJ"):
        return True
    if is_expired(token):
        return True
    if is_expiring_soon(token, lead_sec=lead):
        return True
    return False


def _validate_and_apply(acc: "Account", new_token: str, source: str) -> RefreshResult:
    from .account_runtime import account_context
    from .game_api import get_profile
    from .store import add_account

    if new_token.strip() == (acc.token or "").strip():
        return RefreshResult(acc.name, False, source, "aynı token")

    claim_id = player_id_from_token(new_token)
    if acc.player_id and claim_id and claim_id != str(acc.player_id):
        return RefreshResult(
            acc.name,
            False,
            source,
            f"player_id uyuşmuyor ({claim_id} != {acc.player_id})",
        )

    def _fetch():
        with account_context(proxy_id=acc.proxy_id, proxy_url=acc.proxy_url or None):
            return get_profile(new_token)

    try:
        prof = _fetch()
    except Exception as e:
        return RefreshResult(acc.name, False, source, f"profil doğrulama: {e}")

    if acc.player_id and prof.player_id and prof.player_id != acc.player_id:
        return RefreshResult(acc.name, False, source, "profil player_id farklı")

    add_account(
        acc.name,
        new_token,
        prof.player_id or acc.player_id,
        prof.username or acc.username,
        acc.proxy_id,
        acc.proxy_url,
        telegram_user_id=acc.telegram_user_id,
    )
    record_token_saved(acc.name, new_token)
    from .token_watch import consume_inbox_for_account

    consume_inbox_for_account(acc.name)
    left = format_expiry_human(new_token)
    log.info("token refresh OK acc=%s source=%s exp=%s", acc.name, source, left)
    return RefreshResult(acc.name, True, source, f"yenilendi — kalan: {left}")


def _try_sources_for_account(
    acc: "Account",
    *,
    inbox: dict[str, str],
    legacy_token: str | None,
) -> RefreshResult | None:
    if legacy_token and token_matches_account(
        legacy_token, player_id=acc.player_id, account_name=acc.name
    ):
        res = _validate_and_apply(acc, legacy_token, "legacy_auth")
        if res.ok:
            return res

    inbox_tok = pick_inbox_token(acc.name, acc.player_id, inbox)
    if inbox_tok:
        res = _validate_and_apply(acc, inbox_tok, "token_inbox")
        if res.ok:
            return res

    creds = load_login(acc.name)
    if creds:
        email, password = creds
        token, err = login_for_token(email, password)
        if token:
            res = _validate_and_apply(acc, token, "api_login")
            if res.ok:
                return res
        log.info("api_login failed acc=%s: %s", acc.name, err)

    return None


def refresh_account(acc: "Account", *, force: bool = False) -> RefreshResult:
    if not force and not should_refresh_account(acc):
        left = expires_in_sec(acc.token or "")
        return RefreshResult(
            acc.name,
            False,
            "",
            f"gerek yok (kalan {int(left or 0)}s)",
        )

    inbox = scan_token_inbox(force=force)
    legacy = read_legacy_auth_token(force=force)
    hit = _try_sources_for_account(acc, inbox=inbox, legacy_token=legacy)
    if hit:
        return hit
    return RefreshResult(acc.name, False, "", "kaynak bulunamadı")


def try_silent_refresh(acc: "Account") -> bool:
    """401 öncesi hızlı yenileme — inbox/legacy/login."""
    res = refresh_account(acc, force=True)
    return res.ok


def run_refresh_cycle(*, force_all: bool = False) -> list[RefreshResult]:
    from .store import list_accounts

    results: list[RefreshResult] = []
    inbox = scan_token_inbox()
    legacy = read_legacy_auth_token()
    for acc in list_accounts():
        if not force_all and not should_refresh_account(acc):
            continue
        hit = _try_sources_for_account(acc, inbox=inbox, legacy_token=legacy)
        if hit:
            results.append(hit)
            continue
        if force_all or should_refresh_account(acc):
            results.append(RefreshResult(acc.name, False, "", "kaynak bulunamadı"))
    return results


def backfill_token_exp_all() -> int:
    """Mevcut JWT'lerden token_exp_at doldur."""
    from .store import list_accounts

    n = 0
    for acc in list_accounts():
        if not acc.token.startswith("eyJ"):
            continue
        if token_exp_unix(acc.token):
            record_token_saved(acc.name, acc.token)
            n += 1
    return n
