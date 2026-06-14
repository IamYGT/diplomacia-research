#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

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
    def test_menu_normalize_home(self):
        self.assertEqual(telegram_ui.normalize_menu_text("🏠 Ana Sayfa"), "dashboard")

    def test_menu_legacy_compat(self):
        self.assertEqual(telegram_ui.normalize_menu_text("📊 Durum"), "dashboard")

    def test_dashboard_has_next_steps(self):
        snap = {
            "username": "YGT",
            "level": 23,
            "class": "kalemiye",
            "province": "Hürmüz",
            "country": "Test",
            "balance": 1000,
            "diamonds": 50,
            "health": 0,
            "pills": 100,
            "work_ready": False,
            "premium": True,
            "passive_available": 4,
            "autofarm": True,
        }
        html = telegram_ui.format_dashboard_html(_acc(), snap)
        self.assertIn("Şimdi ne yapmalı", html)
        self.assertIn("Can Doldur", html)

    def test_help_html(self):
        self.assertIn("Ana Sayfa", telegram_ui.format_help_html())

    def test_reply_keyboard_rows(self):
        kb = telegram_ui.main_reply_keyboard()
        self.assertTrue(kb.is_persistent)
        self.assertEqual(len(kb.keyboard), 3)


if __name__ == "__main__":
    unittest.main()
