#!/usr/bin/env python3
"""account_pool birim testleri."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import account_pool


class AccountPoolTests(unittest.TestCase):
    def test_default_rules(self):
        with patch.object(account_pool, "RULES_PATH", Path("/nonexistent/rules.yaml")):
            rules = account_pool.load_rules()
        self.assertGreaterEqual(rules.min_request_delay_sec, 6)
        self.assertEqual(rules.max_accounts_per_egress, 2)

    def test_suggest_proxy_respects_capacity(self):
        with patch.object(account_pool, "RULES_PATH", Path("/nonexistent/rules.yaml")):
            slot = account_pool.suggest_proxy({"a": "direct"})
        self.assertIsNotNone(slot.id)

    def test_count_on_proxy(self):
        n = account_pool.count_on_proxy("direct", {"a": "direct", "b": "egress-1", "c": "direct"})
        self.assertEqual(n, 2)


if __name__ == "__main__":
    unittest.main()
