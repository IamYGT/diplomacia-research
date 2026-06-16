#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.token_console import (
    CONSOLE_GRAB_TOKEN_ONELINER,
    format_console_script_telegram,
    validate_oneliner_js,
)


class TokenConsoleTests(unittest.TestCase):
    def test_oneliner_contains_grab_logic(self):
        self.assertIn("localStorage", CONSOLE_GRAB_TOKEN_ONELINER)
        self.assertIn("execCommand", CONSOLE_GRAB_TOKEN_ONELINER)
        self.assertIn("prompt", CONSOLE_GRAB_TOKEN_ONELINER)

    def test_oneliner_valid_javascript(self):
        validate_oneliner_js()

    def test_oneliner_no_fragile_double_pipe(self):
        self.assertNotIn("||''", CONSOLE_GRAB_TOKEN_ONELINER)
        self.assertIn("s?s:''", CONSOLE_GRAB_TOKEN_ONELINER)

    def test_telegram_message_includes_script(self):
        body = format_console_script_telegram()
        self.assertIn(CONSOLE_GRAB_TOKEN_ONELINER, body)
        self.assertIn("F12", body)
        self.assertLess(len(body), 4096)


if __name__ == "__main__":
    unittest.main()
