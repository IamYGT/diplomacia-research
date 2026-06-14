from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, TypeVar

from .account_pool import prepare_egress
from .stealth_client import reset_request_proxy, set_request_proxy
from .store import Account

T = TypeVar("T")


@contextmanager
def account_context(acc: Account | None = None, *, proxy_id: str = "", proxy_url: str | None = None):
    """Hesap proxy'si + Tor NEWNYM context."""
    pid = proxy_id or (acc.proxy_id if acc else "")
    purl = proxy_url if proxy_url is not None else (acc.proxy_url if acc else None)
    if pid:
        prepare_egress(pid)
    tok = set_request_proxy(purl or None)
    try:
        yield
    finally:
        reset_request_proxy(tok)


def run_for_account(acc: Account, fn: Callable[..., T], *args, **kwargs) -> T:
    with account_context(acc):
        return fn(*args, **kwargs)
