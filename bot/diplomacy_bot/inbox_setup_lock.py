"""Fleet inbox setup lock — cross-process uid guard."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DATA_DIR

_LOCK_DIR = DATA_DIR / "locks"
_STALE_SEC = 15 * 60


def _lock_path(telegram_user_id: int) -> Path:
    return _LOCK_DIR / f"fleet_inbox_setup_{int(telegram_user_id)}.lock"


@contextmanager
def acquire_inbox_setup_lock(telegram_user_id: int, *, stale_sec: int = _STALE_SEC) -> Iterator[bool]:
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    path = _lock_path(telegram_user_id)
    fd: int | None = None
    try:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(time.time()).encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > stale_sec:
                    path.unlink(missing_ok=True)
                    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, str(time.time()).encode("ascii"))
                else:
                    yield False
                    return
            except OSError:
                yield False
                return
        yield True
    finally:
        if fd is not None:
            os.close(fd)
            path.unlink(missing_ok=True)
