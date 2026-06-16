#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.crash_notify import format_crash_report, send_crash_notify
from diplomacy_bot.version import get_version_label


class CrashNotifyTests(unittest.TestCase):
    def test_format_contains_version(self):
        text = format_crash_report("Test crash", "detail", exc=ValueError("boom"), tb="File x, line 1\nValueError: boom")
        self.assertIn("Test crash", text)
        self.assertIn("boom", text)
        self.assertIn(get_version_label(), text)

    @patch("diplomacy_bot.crash_notify.requests.post")
    @patch("diplomacy_bot.crash_notify.TELEGRAM_ADMIN_IDS", {515491882})
    @patch("diplomacy_bot.crash_notify.TELEGRAM_BOT_TOKEN", "123:ABC")
    def test_send_ok(self, mock_post):
        mock_post.return_value.json.return_value = {"ok": True}
        ok = send_crash_notify("Ping", "test", dedupe_key="test-send-unique")
        self.assertTrue(ok)
        mock_post.assert_called()


if __name__ == "__main__":
    unittest.main()
