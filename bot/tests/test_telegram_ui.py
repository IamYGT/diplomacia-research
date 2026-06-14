#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.store import Account
from diplomacy_bot import telegram_ui


def _acc() -> Account:
    return Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="YGT",
        autofarm=True,
        last_farm_at=0,
        last_balance=0,
        proxy_id="tor-01",
        proxy_url="",
        status="active",
    )


class TelegramUiTests(unittest.TestCase):
    def test_menu_normalize(self):
        self.assertEqual(telegram_ui.normalize_menu_text("📊 Durum"), "ne durumdayım")

    def test_dashboard_html_escapes(self):
        snap = {
            "username": "Test<script>",
            "level": 5,
            "class": "kalemiye",
            "province": "Hürmüz",
            "balance": 1000,
            "diamonds": 50,
            "health": 80,
            "pills": 10,
            "work_ready": True,
            "premium": True,
            "passive_available": 3,
            "autofarm": True,
        }
        html = telegram_ui.format_dashboard_html(_acc(), snap)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("3.1.0", html)

    def test_reply_keyboard_rows(self):
        kb = telegram_ui.main_reply_keyboard()
        self.assertTrue(kb.is_persistent)
        self.assertEqual(len(kb.keyboard), 3)


if __name__ == "__main__":
    unittest.main()
