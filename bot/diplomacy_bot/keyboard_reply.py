"""Kullanıcıya özel reply klavye — ContextVar + handler sarmalayıcı."""

from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, AsyncIterator, Callable

from .keyboard_prefs import reply_keyboard_for_user

_telegram_uid: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "telegram_uid", default=None
)


def install_global_reply_keyboard() -> None:
    from . import telegram_ui as ui

    if getattr(ui, "_global_kb_installed", False):
        return

    _orig = ui.main_reply_keyboard

    def main_reply_keyboard() -> Any:
        uid = _telegram_uid.get()
        if uid:
            kb = reply_keyboard_for_user(uid)
            if kb is not None:
                return kb
        return _orig()

    ui.main_reply_keyboard = main_reply_keyboard  # type: ignore[assignment]
    ui._global_kb_installed = True


def with_user_keyboard(handler: Callable) -> Callable:
    @wraps(handler)
    async def wrapper(update, context, *args, **kwargs):
        uid = update.effective_user.id if update and update.effective_user else 0
        async with user_reply_keyboard(uid):
            return await handler(update, context, *args, **kwargs)

    return wrapper


@asynccontextmanager
async def user_reply_keyboard(uid: int) -> AsyncIterator[None]:
    token = _telegram_uid.set(uid)
    try:
        yield
    finally:
        _telegram_uid.reset(token)


def patch_all_handler_keyboards() -> None:
    """Tüm komut + mesaj/callback handler'larına uid bağlı klavye."""
    from . import telegram_app as ta

    if getattr(ta, "_all_handlers_kb_patched", False):
        return

    install_global_reply_keyboard()

    for name in list(vars(ta)):
        if not name.startswith("cmd_"):
            continue
        fn = getattr(ta, name, None)
        if callable(fn) and not getattr(fn, "_kb_wrapped", False):
            wrapped = with_user_keyboard(fn)
            wrapped._kb_wrapped = True  # type: ignore[attr-defined]
            setattr(ta, name, wrapped)

    for attr in ("on_text", "on_callback"):
        fn = getattr(ta, attr, None)
        if callable(fn) and not getattr(fn, "_kb_wrapped", False):
            wrapped = with_user_keyboard(fn)
            wrapped._kb_wrapped = True  # type: ignore[attr-defined]
            setattr(ta, attr, wrapped)

    ta._all_handlers_kb_patched = True
