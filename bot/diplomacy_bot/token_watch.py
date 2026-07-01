"""Harici token kaynakları — LEGACY_AUTH + token_inbox dizini."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import DATA_DIR, LEGACY_AUTH
from .jwt_meta import player_id_from_token
from .token_extract import extract_jwt_from_text

log = logging.getLogger(__name__)

TOKEN_INBOX = DATA_DIR / "token_inbox"
_inbox_mtime: dict[str, float] = {}
_legacy_mtime: float = 0.0


def _read_token_from_path(path: Path) -> str | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return None
    if raw.startswith("eyJ"):
        return raw.splitlines()[0].strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            tok = data.get("token", "")
            if isinstance(tok, str) and tok.startswith("eyJ"):
                return tok.strip()
        except json.JSONDecodeError:
            pass
    return extract_jwt_from_text(raw)


def read_legacy_auth_token(*, force: bool = False) -> str | None:
    """LEGACY_AUTH dosyası değiştiyse token döndür."""
    global _legacy_mtime
    if not LEGACY_AUTH.exists():
        return None
    mtime = LEGACY_AUTH.stat().st_mtime
    if not force and mtime <= _legacy_mtime:
        return None
    _legacy_mtime = mtime
    tok = _read_token_from_path(LEGACY_AUTH)
    if tok:
        log.info("LEGACY_AUTH token okundu mtime=%s", mtime)
    return tok


def scan_token_inbox(*, force: bool = False) -> dict[str, str]:
    """Hesap adı veya player_id → yeni token (mtime değiştiyse)."""
    TOKEN_INBOX.mkdir(parents=True, exist_ok=True)
    found: dict[str, str] = {}
    for path in sorted(TOKEN_INBOX.glob("*")):
        try:
            if not path.is_file():
                continue
            key = path.name.lower()
            if key.endswith(".jwt"):
                key = key[:-4]
            elif key.endswith(".txt"):
                key = key[:-4]
            mtime = path.stat().st_mtime
            prev = _inbox_mtime.get(str(path), 0.0)
            if not force and mtime <= prev:
                continue
            tok = _read_token_from_path(path)
            if not tok:
                continue
        except Exception as e:
            log.warning("token_inbox scan skip %s: %s", path.name, e)
            continue
        _inbox_mtime[str(path)] = mtime
        found[key] = tok
        log.info("token_inbox %s → %s…", path.name, tok[:12])
    return found


def token_matches_account(token: str, *, player_id: str, account_name: str) -> bool:
    claim_id = player_id_from_token(token)
    if player_id and claim_id and claim_id == str(player_id):
        return True
    if account_name and claim_id and claim_id == account_name:
        return True
    return False


def consume_inbox_for_account(account_name: str) -> bool:
    """DB'ye yazıldıktan sonra eşleşen inbox dosyalarını sil."""
    name = account_name.strip().lower()
    TOKEN_INBOX.mkdir(parents=True, exist_ok=True)
    removed = False
    for path in list(TOKEN_INBOX.iterdir()):
        if not path.is_file():
            continue
        key = path.name.lower()
        for suffix in (".jwt", ".txt"):
            if key.endswith(suffix):
                key = key[: -len(suffix)]
                break
        if key == name or key.startswith(f"{name}_"):
            try:
                path.unlink()
                _inbox_mtime.pop(str(path), None)
                log.info("token_inbox consumed %s", path.name)
                removed = True
            except OSError as e:
                log.warning("token_inbox consume fail %s: %s", path.name, e)
    return removed


def pick_inbox_token(
    account_name: str,
    player_id: str,
    inbox: dict[str, str],
) -> str | None:
    name = account_name.strip().lower()
    if name in inbox:
        tok = inbox[name]
        if token_matches_account(tok, player_id=player_id, account_name=name):
            return tok
    pid = str(player_id or "").strip()
    if pid and pid in inbox:
        tok = inbox[pid]
        if token_matches_account(tok, player_id=pid, account_name=name):
            return tok
    for tok in inbox.values():
        if token_matches_account(tok, player_id=player_id, account_name=name):
            return tok
    return None


def _inbox_key_to_account_name(key: str, telegram_user_id: int) -> str | None:
    """token_inbox dosya adı → hesap adı (yalnızca u{uid} alanı)."""
    k = key.strip().lower()
    prefix = f"u{telegram_user_id}"
    if k == prefix or k.startswith(f"{prefix}_"):
        return k
    return None


def list_inbox_import_candidates(telegram_user_id: int) -> list[tuple[str, str]]:
    """Inbox'taki yeni tokenlar — (hesap_adı, jwt)."""
    inbox = scan_token_inbox(force=True)
    if not inbox:
        return []
    out: list[tuple[str, str]] = []
    for key, tok in sorted(inbox.items()):
        name = _inbox_key_to_account_name(key, telegram_user_id)
        if not name or not tok:
            continue
        out.append((name, tok))
    return out


def list_fresh_inbox_import_candidates(telegram_user_id: int) -> list[tuple[str, str]]:
    """Auto-setup için henüz processed olmayan inbox adayları."""
    from .inbox_processed_state import is_inbox_candidate_processed

    return [
        (name, token)
        for name, token in list_inbox_import_candidates(telegram_user_id)
        if not is_inbox_candidate_processed(telegram_user_id, name, token)
    ]


def list_inbox_operator_uids() -> list[int]:
    """token_inbox'taki u{uid}_* dosyalarından operatör Telegram id listesi."""
    import re

    TOKEN_INBOX.mkdir(parents=True, exist_ok=True)
    uids: set[int] = set()
    for path in TOKEN_INBOX.glob("*"):
        if not path.is_file():
            continue
        key = path.name.lower()
        for suffix in (".jwt", ".txt"):
            if key.endswith(suffix):
                key = key[: -len(suffix)]
                break
        m = re.match(r"u(\d+)(?:_|$)", key)
        if m:
            uids.add(int(m.group(1)))
    return sorted(uids)
