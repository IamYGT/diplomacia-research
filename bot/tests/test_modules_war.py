#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import war


class WarTests(unittest.TestCase):
    def test_skipped_when_disabled(self):
        cfg = AccountConfig(account_name="a", war_enabled=False)
        self.assertIsNone(war.try_contribute("tok", cfg, _api=lambda *a, **k: (200, {})))

    def test_contribute_first_war(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/wars/my-country":
                return 200, {"wars": [{"id": "w1", "my_side": "defender"}]}
            if p.endswith("/contribute"):
                return 200, {"ok": True}
            return 404, {}

        cfg = AccountConfig(account_name="a", war_enabled=True, contribute_side="auto")
        r = war.try_contribute("tok", cfg, _api=api)
        self.assertTrue(r["ok"])
        self.assertEqual(r["side"], "defender")


if __name__ == "__main__":
    unittest.main()
