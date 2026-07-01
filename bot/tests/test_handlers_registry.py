"""Handler registry testleri (M10)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_register_command_handlers_count():
    from diplomacy_bot.handlers.registry import _COMMANDS, register_command_handlers

    app = MagicMock()
    register_command_handlers(app)
    assert app.add_handler.call_count == len(_COMMANDS)


def test_cmd_onboarding_reexported_on_telegram_app():
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.handlers.cmd_onboarding import send_connect_package

    assert ta._send_connect_package is send_connect_package
    assert callable(ta.cmd_start)
    assert callable(ta.cmd_connect)
