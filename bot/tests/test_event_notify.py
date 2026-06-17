#!/usr/bin/env python3
"""event_notify — Telegram push + dedup regression."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import event_notify


class EventNotifyTests(unittest.TestCase):
    def setUp(self):
        event_notify.reset_dedup()

    def test_dedup_blocks_repeat_within_cooldown(self):
        calls = {"n": 0}

        def fake_send(chat_id, text):
            calls["n"] += 1
            return True

        with patch("diplomacy_bot.event_notify.send_telegram_message", side_effect=fake_send):
            r1 = event_notify.notify_event(42, "war:ygt:1", "Savaş", "Ülke saldırıda")
            r2 = event_notify.notify_event(42, "war:ygt:1", "Savaş", "Ülke saldırıda")
        self.assertTrue(r1)
        self.assertFalse(r2)  # dedup
        self.assertEqual(calls["n"], 1)

    def test_different_event_keys_not_deduped(self):
        calls = {"n": 0}

        def fake_send(chat_id, text):
            calls["n"] += 1
            return True

        with patch("diplomacy_bot.event_notify.send_telegram_message", side_effect=fake_send):
            event_notify.notify_event(42, "war:ygt:1", "Savaş", "a")
            event_notify.notify_event(42, "quest:ygt", "Quest", "b")
        self.assertEqual(calls["n"], 2)

    def test_failed_send_not_marked_dedup(self):
        """Gönderim başarısızsa dedup set edilmez — yeniden denenebilir."""
        with patch("diplomacy_bot.event_notify.send_telegram_message", return_value=False):
            r1 = event_notify.notify_event(42, "war:ygt:1", "Savaş", "x")

        calls = {"n": 0}

        def fake_send(chat_id, text):
            calls["n"] += 1
            return True

        with patch("diplomacy_bot.event_notify.send_telegram_message", side_effect=fake_send):
            r2 = event_notify.notify_event(42, "war:ygt:1", "Savaş", "x")
        self.assertFalse(r1)
        self.assertTrue(r2)  # ilk başarısız → dedup yok → ikinci gönderilir
        self.assertEqual(calls["n"], 1)

    def test_send_telegram_message_no_token(self):
        """Token yoksa güvenli False."""
        with patch("diplomacy_bot.event_notify._bot_token", return_value=""):
            self.assertFalse(event_notify.send_telegram_message(42, "x"))

    def test_text_format(self):
        captured = {}

        def fake_send(chat_id, text):
            captured["text"] = text
            return True

        with patch("diplomacy_bot.event_notify.send_telegram_message", side_effect=fake_send):
            event_notify.notify_event(42, "k1", "Başlık", "Detay")
        self.assertIn("<b>Başlık</b>", captured["text"])
        self.assertIn("Detay", captured["text"])


if __name__ == "__main__":
    unittest.main()
