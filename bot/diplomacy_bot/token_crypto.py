"""JWT at-rest şifreleme (Fernet)."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_ENC_PREFIX = "enc:"
_FERNET = None
_SECRET_PATH: Path | None = None


def _secret_file(data_dir: Path) -> Path:
    return data_dir / ".db_secret"


def _derive_fernet_key(raw: bytes) -> bytes:
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def init_token_crypto(data_dir: Path, env_secret: str = "") -> None:
    """Fernet anahtarını yükle veya oluştur."""
    global _FERNET, _SECRET_PATH
    from cryptography.fernet import Fernet

    _SECRET_PATH = _secret_file(data_dir)
    secret = (env_secret or os.environ.get("BOT_DB_SECRET", "")).strip()
    if not secret and _SECRET_PATH.exists():
        secret = _SECRET_PATH.read_text(encoding="utf-8").strip()
    if not secret:
        secret = Fernet.generate_key().decode("ascii")
        data_dir.mkdir(parents=True, exist_ok=True)
        _SECRET_PATH.write_text(secret, encoding="utf-8")
        try:
            _SECRET_PATH.chmod(0o600)
        except OSError:
            pass
        log.warning("BOT_DB_SECRET yok — %s oluşturuldu (yedekle!)", _SECRET_PATH)
    elif len(secret) != 44 or not secret.endswith("="):
        secret = _derive_fernet_key(secret.encode("utf-8")).decode("ascii")
    _FERNET = Fernet(secret.encode("ascii") if isinstance(secret, str) else secret)


def _fernet():
    if _FERNET is None:
        from .config import BOT_DB_SECRET, DATA_DIR

        init_token_crypto(DATA_DIR, BOT_DB_SECRET)
    return _FERNET


def encrypt_token(plain: str) -> str:
    if not plain or not plain.strip():
        return ""
    token = plain.strip()
    if token.startswith("eyJ"):
        return _fernet().encrypt(token.encode("utf-8")).decode("ascii")
    return token


def decrypt_token(stored: str) -> str:
    if not stored:
        return ""
    if stored.startswith("eyJ"):
        return stored
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except Exception:
        log.exception("token decrypt failed")
        return ""


def is_encrypted_blob(stored: str) -> bool:
    return bool(stored) and not stored.startswith("eyJ")
