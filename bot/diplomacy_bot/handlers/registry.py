"""Telegram komut handler kaydı (M10)."""

from __future__ import annotations

from telegram.ext import CommandHandler

_COMMANDS: tuple[str, ...] = (
    "start",
    "connect",
    "menu",
    "dashboard",
    "fleet",
    "setrole",
    "settings",
    "help",
    "whoami",
    "version",
    "setaccount",
    "accounts",
    "add",
    "remove",
    "status",
    "farm",
    "setfabric",
    "setwar",
    "setstat",
    "plan",
    "autofarm",
    "daily",
    "ping",
    "report",
    "proxies",
    "setproxy",
    "intel",
    "cooldown",
    "endpoints",
    "api",
    "play",
    "ai",
    "confirm",
    "cancel",
)


def register_command_handlers(app) -> None:
    from diplomacy_bot import telegram_app as ta

    for name in _COMMANDS:
        handler = getattr(ta, f"cmd_{name}")
        app.add_handler(CommandHandler(name, handler))
