from __future__ import annotations

import contextvars
import json
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any

from .account_pool import load_rules

_request_proxy: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_proxy", default=None)
_interactive_fast: contextvars.ContextVar[bool] = contextvars.ContextVar("interactive_fast", default=False)
_last_429_at: float = 0.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def set_request_proxy(proxy_url: str | None) -> contextvars.Token:
    return _request_proxy.set(proxy_url or None)


def reset_request_proxy(token: contextvars.Token) -> None:
    _request_proxy.reset(token)


def set_interactive_fast(enabled: bool = True) -> contextvars.Token:
    """Telegram buton/tuş — kısa delay (autofarm arka planı yavaş kalır)."""
    return _interactive_fast.set(enabled)


def reset_interactive_fast(token: contextvars.Token) -> None:
    _interactive_fast.reset(token)


def is_interactive_fast() -> bool:
    return bool(_interactive_fast.get())


def get_request_proxy() -> str | None:
    p = _request_proxy.get()
    if p:
        return p
    return os.environ.get("PROXY_URL") or None


def _http_via_requests(
    method: str,
    url: str,
    headers: dict[str, str],
    data: bytes | None,
    proxy: str,
    timeout: int,
) -> tuple[int, str]:
    import requests

    proxies = {"http": proxy, "https": proxy}
    r = requests.request(
        method.upper(),
        url,
        headers=headers,
        data=data,
        proxies=proxies,
        timeout=timeout,
    )
    return r.status_code, r.text


def _is_throttle(code: int, body: str) -> bool:
    if code == 429:
        return True
    low = body.lower()
    return "fazla istek" in low or "retryafter" in low or "too many" in low


def _parse_retry_after(body: str) -> int:
    try:
        return int(json.loads(body).get("retryAfter", 90))
    except Exception:
        return 90


def stealth_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    delay: float | None = None,
    timeout: int = 40,
) -> tuple[int, str]:
    """HTTP isteği — SOCKS proxy (Tor), stealth delay, 429 backoff."""
    global _last_429_at
    rules = load_rules()
    fast = _interactive_fast.get()
    if fast:
        base = 0.0 if delay is None else float(delay)
        wait = min(base, 0.15)
        jitter = random.uniform(0, 0.05)
        cap = int(os.environ.get("INTERACTIVE_API_TIMEOUT_SEC", "15"))
        timeout = min(timeout, cap) if cap > 0 else timeout
    else:
        wait = delay if delay is not None else rules.min_request_delay_sec
        jitter = random.uniform(0, 1.5)
    time.sleep(wait + jitter)

    since_429 = time.time() - _last_429_at
    if since_429 < rules.cooldown_on_429_sec:
        remaining = rules.cooldown_on_429_sec - since_429
        if fast:
            ra = int(remaining) + 1
            return 429, json.dumps({"error": "rate_limited", "retryAfter": ra, "message": f"API limiti ({ra}s)"})
        time.sleep(remaining)

    hdrs = {
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "User-Agent": random.choice(USER_AGENTS),
    }
    if headers:
        hdrs.update(headers)

    proxy = get_request_proxy()
    use_socks = proxy and proxy.startswith("socks")

    for attempt in range(4):
        try:
            if use_socks:
                st, body = _http_via_requests(method, url, hdrs, data, proxy, timeout)
            else:
                req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    st, body = r.status, r.read().decode(errors="replace")
            if _is_throttle(st, body):
                # 429: cooldown set et, hemen dön. Eski kod sleep(ra+5) × 3 retry yapıp
                # arka plan job'larını ~5dk blokluyordu (290sn). Job'lar periyodik —
                # sonraki tick cooldown sonrası tekrar dener, retry'ya gerek yok.
                _last_429_at = time.time()
                return st, body
            return st, body
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if _is_throttle(e.code, body):
                # 429: cooldown set et, hemen dön (üstteki throttle dalıyla aynı gerekçe).
                _last_429_at = time.time()
                return e.code, body
            return e.code, body
        except Exception as e:
            if attempt < 3:
                time.sleep(3)
                continue
            return 0, str(e)[:300]
    return 0, "max retries"


def cooldown_remaining_sec() -> int:
    rules = load_rules()
    elapsed = time.time() - _last_429_at
    if elapsed >= rules.cooldown_on_429_sec:
        return 0
    return int(rules.cooldown_on_429_sec - elapsed)
