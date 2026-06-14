from __future__ import annotations

import subprocess
import time
from pathlib import Path

COOKIE_PATH = Path("/var/run/tor/control.authcookie")
CONTROL_SOCK = "/var/run/tor/control"
TOR_SOCKS = "socks5h://127.0.0.1:9050"
_last_rotate_at = 0.0
MIN_ROTATE_INTERVAL = 10.0


def rotate_newnym() -> bool:
    """Tor exit IP değiştir (NEWNYM). Başarısızsa False."""
    global _last_rotate_at
    now = time.time()
    if now - _last_rotate_at < MIN_ROTATE_INTERVAL:
        time.sleep(MIN_ROTATE_INTERVAL - (now - _last_rotate_at))
    if not COOKIE_PATH.exists():
        return False
    cookie = COOKIE_PATH.read_bytes().hex()
    script = f"AUTHENTICATE {cookie}\r\nSIGNAL NEWNYM\r\nQUIT\r\n"
    try:
        proc = subprocess.run(
            ["nc", "-U", "-w", "3", CONTROL_SOCK],
            input=script,
            capture_output=True,
            text=True,
            timeout=5,
        )
        ok = "250 OK" in proc.stdout
        if ok:
            _last_rotate_at = time.time()
            time.sleep(4)  # yeni circuit stabilize
        return ok
    except Exception:
        return False


def tor_socks_url() -> str:
    return TOR_SOCKS
