"""Token yapıştırma — doğru hesabı seç, farklı oyuncuyu üzerine yazma."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

from .auth import default_account_name, scoped_list_accounts
from .store import get_account


@dataclass
class TokenConnectPlan:
    action: str  # save | reject
    account_name: str = ""
    message: str = ""
    username: str = ""
    player_id: str = ""


def decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.strip().split(".")
        if len(parts) < 2:
            return {}
        pad = "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _sanitize_alias(username: str) -> str:
    alias = re.sub(r"[^a-z0-9_]", "", (username or "").lower())[:20]
    return alias or "alt"


def suggest_new_account_name(telegram_user_id: int, username: str) -> str:
    return default_account_name(telegram_user_id, _sanitize_alias(username))


def plan_token_connect(
    token: str,
    telegram_user_id: int,
    *,
    pending_add: str | None = None,
    pending_refresh: str | None = None,
    pending_connect: bool = False,
    default_account: str | None = None,
) -> TokenConnectPlan:
    """Hangi hesap adına kaydedileceğini belirle — profil API'si çağıran tarafında."""
    from .account_runtime import account_context
    from .game_api import get_profile

    claims = decode_jwt_payload(token)
    claim_id = str(claims.get("id") or "")
    claim_user = str(claims.get("username") or "")

    def _fetch():
        with account_context(proxy_id="direct", proxy_url=None):
            return get_profile(token)

    try:
        prof = _fetch()
    except Exception as e:
        return TokenConnectPlan(action="reject", message=f"❌ Token geçersiz: {e}")

    player_id = prof.player_id or claim_id
    username = prof.username or claim_user
    accs = scoped_list_accounts(telegram_user_id)

    for acc in accs:
        if acc.player_id and player_id and acc.player_id == player_id:
            return TokenConnectPlan(
                action="save",
                account_name=acc.name,
                username=username,
                player_id=player_id,
            )

    if pending_refresh:
        name = pending_refresh.strip().lower()
        existing = get_account(name)
        if existing and existing.telegram_user_id == telegram_user_id:
            if not existing.player_id or existing.player_id == player_id:
                return TokenConnectPlan(
                    action="save",
                    account_name=name,
                    username=username,
                    player_id=player_id,
                )
            return TokenConnectPlan(
                action="reject",
                message=(
                    f"❌ <b>{name}</b> başka bir oyuncuya ait.\n"
                    f"Bu token: <b>{username}</b>\n\n"
                    f"İkinci hesap için: <code>/add {_sanitize_alias(username)}</code> yaz, sonra token yapıştır."
                ),
            )

    if pending_add:
        name = pending_add.strip().lower()
        existing = get_account(name)
        if existing and existing.telegram_user_id not in (0, telegram_user_id):
            return TokenConnectPlan(
                action="reject",
                message=f"❌ <b>{name}</b> başka bir Telegram kullanıcısına ait.",
            )
        if existing and existing.telegram_user_id == 0:
            from .auth import can_claim_orphan_account

            if not can_claim_orphan_account(name, telegram_user_id):
                return TokenConnectPlan(
                    action="reject",
                    message=(
                        f"❌ <b>{name}</b> legacy hesap adı — claim edilemez.\n"
                        f"Yeni hesap: <code>/add {_sanitize_alias(username)}</code>"
                    ),
                )
        if existing and existing.player_id and existing.player_id != player_id:
            return TokenConnectPlan(
                action="reject",
                message=(
                    f"❌ <b>{name}</b> zaten başka oyuncuya bağlı.\n"
                    f"Farklı isim dene: <code>/add {_sanitize_alias(username)}</code>"
                ),
            )
        return TokenConnectPlan(
            action="save",
            account_name=name,
            username=username,
            player_id=player_id,
        )

    if accs and pending_connect:
        target = (default_account or "").strip().lower()
        if target:
            existing = get_account(target)
            if existing and existing.player_id and existing.player_id != player_id:
                new_name = suggest_new_account_name(telegram_user_id, username)
                return TokenConnectPlan(
                    action="save",
                    account_name=new_name,
                    username=username,
                    player_id=player_id,
                    message=(
                        f"🆕 Farklı oyuncu algılandı: <b>{username}</b>\n"
                        f"Yeni hesap olarak <b>{new_name}</b> ekleniyor.\n"
                        f"<i>({target} silinmedi — eski token'ı tekrar yapıştırarak geri yükleyebilirsin)</i>"
                    ),
                )

    if not accs:
        name = default_account_name(telegram_user_id)
        return TokenConnectPlan(action="save", account_name=name, username=username, player_id=player_id)

    new_name = suggest_new_account_name(telegram_user_id, username)
    return TokenConnectPlan(
        action="save",
        account_name=new_name,
        username=username,
        player_id=player_id,
        message=f"🆕 Yeni hesap: <b>{new_name}</b> ({username})",
    )


def format_account_connected_html(
    acc_name: str, prof, *, telegram_user_id: int, is_new_account: bool = False
) -> str:
    """Bağlantı başarı mesajı — farm ipuçları dahil."""
    import html

    from .store import count_accounts_for_user
    from .auto_defaults import auto_features_summary

    name = html.escape(acc_name.strip().lower())
    user = html.escape(str(prof.username))
    lines = [
        f"✅ <b>{name}</b> bağlandı — {user}",
        f"💰 {int(prof.balance):,} | lv{int(prof.level)}",
        "",
        "🏠 Ana Sayfa ile panele geç.",
    ]
    if is_new_account:
        lines.extend(["", auto_features_summary()])
    if count_accounts_for_user(telegram_user_id) >= 2:
        lines.extend(
            [
                "",
                "💡 <b>İkinci hesap</b> için:",
                f"<code>/setrole {name} farm</code>",
                f"<code>/setfabric {name} foreign</code> veya <code>world</code>",
            ]
        )
    return "\n".join(lines)
