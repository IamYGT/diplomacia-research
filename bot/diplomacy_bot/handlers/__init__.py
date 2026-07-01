"""Telegram command handlers package (M10)."""

from .cmd_accounts import (
    cmd_accounts,
    cmd_add,
    cmd_remove,
    cmd_setaccount,
    cmd_status,
    cmd_whoami,
)
from .cmd_onboarding import cmd_connect, cmd_start, send_connect_package
from .registry import register_command_handlers

__all__ = [
    "cmd_accounts",
    "cmd_add",
    "cmd_connect",
    "cmd_remove",
    "cmd_setaccount",
    "cmd_start",
    "cmd_status",
    "cmd_whoami",
    "register_command_handlers",
    "send_connect_package",
]
