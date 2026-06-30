#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.runtime_install import patch_easy_mode_ui
from diplomacy_bot.store import Account
from diplomacy_bot import telegram_ui

patch_easy_mode_ui()


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

    def test_menu_easy_war(self):
        self.assertEqual(telegram_ui.normalize_menu_text("⚔️ Savaşa Vur"), "savaşa vur")

    def test_menu_war_tab(self):
        self.assertEqual(telegram_ui.normalize_menu_text("⚔️ Savaş"), "war_tab")

    def test_menu_travel_tab(self):
        self.assertEqual(telegram_ui.normalize_menu_text("🚶 Seyahat"), "travel_tab")

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
            "quests_claimable": 2,
            "training_ready": True,
        }
        html = telegram_ui.format_dashboard_html(_acc(), snap)
        self.assertIn("Sıradaki işin", html)
        self.assertIn("Can Doldur", html)
        self.assertIn("görev", html)
        self.assertIn("Hazır:", html)

    def test_dashboard_work_countdown(self):
        snap = {
            "username": "YGT",
            "level": 1,
            "class": "x",
            "province": "p",
            "country": "c",
            "balance": 0,
            "diamonds": 0,
            "health": 100,
            "pills": 0,
            "work_ready": False,
            "work_wait_ms": 45_000,
            "passive_available": 0,
            "autofarm": False,
        }
        html = telegram_ui.format_dashboard_html(_acc(), snap)
        self.assertIn("45 sn", html)

    def test_help_html(self):
        self.assertIn("Altın", telegram_ui.format_help_html())

    def test_reply_keyboard_rows(self):
        kb = telegram_ui.main_reply_keyboard()
        self.assertTrue(kb.is_persistent)
        self.assertEqual(len(kb.keyboard), 4)


if __name__ == "__main__":
    unittest.main()
