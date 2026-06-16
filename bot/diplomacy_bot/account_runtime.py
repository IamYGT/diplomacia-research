from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, TypeVar

from .account_pool import prepare_egress
from .stealth_client import (
    reset_interactive_fast,
    reset_request_proxy,
    set_interactive_fast,
    set_request_proxy,
)
from .store import Account

T = TypeVar("T")


@contextmanager
def account_context(
    acc: Account | None = None,
    *,
    proxy_id: str = "",
    proxy_url: str | None = None,
    rotate_egress: bool = False,
):
    """Hesap proxy'si + isteğe bağlı Tor NEWNYM (yalnızca farm/tick yazma işleri)."""
    pid = proxy_id or (acc.proxy_id if acc else "")
    purl = proxy_url if proxy_url is not None else (acc.proxy_url if acc else None)
    if pid and rotate_egress:
        prepare_egress(pid)
    tok = set_request_proxy(purl or None)
    try:
        yield
    finally:
        reset_request_proxy(tok)


def run_for_account(acc: Account, fn: Callable[..., T], *args, **kwargs) -> T:
    with account_context(acc):
        return fn(*args, **kwargs)


def interactive_run(acc: Account, fn: Callable[..., T], *args, **kwargs) -> T:
    with interactive_account_context(acc):
        return fn(*args, **kwargs)


@contextmanager
def interactive_account_context(acc: Account | None = None, *, proxy_id: str = "", proxy_url: str | None = None):
    """UI tetikli işlemler — düşük API delay + hesap proxy."""
    with account_context(acc, proxy_id=proxy_id, proxy_url=proxy_url):
        fast_tok = set_interactive_fast(True)
        try:
            yield
        finally:
            reset_interactive_fast(fast_tok)
