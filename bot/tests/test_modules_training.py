#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import training


class TrainingTests(unittest.TestCase):
    def test_skipped_when_disabled(self):
        cfg = AccountConfig(account_name="a", training_enabled=False)
        self.assertIsNone(training.try_free_attack("tok", cfg, _api=lambda *a, **k: (200, {})))

    def test_attack_when_ready(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/auto/status":
                return 200, {"free_attack_available": True}
            if p == "/training-wars/my":
                return 200, {"id": "tw-1", "name": "Test"}
            if p.endswith("/attack"):
                return 200, {"damage": 10}
            return 404, {}

        cfg = AccountConfig(account_name="a")
        r = training.try_free_attack("tok", cfg, _api=api)
        self.assertTrue(r["ok"])

    def test_attack_cooldown_response_is_retryable_skip(self):
        def api(m, p, t, body=None, delay=0):
            if p.endswith("/attack"):
                return 429, {"remaining_ms": 180000}
            return 404, {}

        r = training.attack_training("tok", "tw-1", _api=api)
        self.assertFalse(r["ok"])
        self.assertEqual(r["skipped"], "free_attack_cooldown")
        self.assertEqual(r["ms"], 180000)

    def test_attack_http_error_is_named_skip(self):
        def api(m, p, t, body=None, delay=0):
            if p.endswith("/attack"):
                return 500, {"error": "temporary"}
            return 404, {}

        r = training.attack_training("tok", "tw-1", _api=api)
        self.assertFalse(r["ok"])
        self.assertEqual(r["skipped"], "training_attack_error")
        self.assertEqual(r["status"], 500)


if __name__ == "__main__":
    unittest.main()
