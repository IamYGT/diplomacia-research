#!/usr/bin/env python3
"""profile cache + upgrade 429 throttle regresyon — rate limit dayanıklılık."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import game_api
from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import stats


def _profile_payload(balance: int = 5) -> dict:
    return {"player": {"id": "1", "username": "U", "balance": balance, "level": 1}}


class ProfileCacheTests(unittest.TestCase):
    def setUp(self):
        game_api.invalidate_profile_cache()

    def test_cache_hit_skips_api(self):
        calls = {"n": 0}

        def fake_api(method, path, token, **kw):
            calls["n"] += 1
            return 200, _profile_payload()

        with patch("diplomacy_bot.game_api.api", side_effect=fake_api):
            game_api.get_profile("tok")
            game_api.get_profile("tok")  # cache hit
        self.assertEqual(calls["n"], 1, "cache hit API çağırmamalı")

    def test_fresh_bypasses_cache(self):
        calls = {"n": 0}

        def fake_api(method, path, token, **kw):
            calls["n"] += 1
            return 200, _profile_payload(balance=calls["n"] * 10)

        with patch("diplomacy_bot.game_api.api", side_effect=fake_api):
            game_api.get_profile("tok")
            p = game_api.get_profile("tok", fresh=True)
        self.assertEqual(calls["n"], 2)
        self.assertEqual(p.balance, 20)  # fresh yeni balance

    def test_invalidate_clears_cache(self):
        calls = {"n": 0}

        def fake_api(method, path, token, **kw):
            calls["n"] += 1
            return 200, _profile_payload()

        with patch("diplomacy_bot.game_api.api", side_effect=fake_api):
            game_api.get_profile("tok")
            game_api.invalidate_profile_cache("tok")
            game_api.get_profile("tok")
        self.assertEqual(calls["n"], 2, "invalidate sonrası API çağrılmalı")


class UpgradeThrottleTests(unittest.TestCase):
    def setUp(self):
        stats._LAST_UPGRADE_429_AT = 0.0

    def test_throttle_active_skips_upgrade(self):
        """429 sonrası 10dk içinde run_stat_automation upgrade denemez."""
        stats._LAST_UPGRADE_429_AT = time.time()
        cfg = AccountConfig("t", stat_auto_enabled=True)
        with patch("diplomacy_bot.modules.stats.spend_available") as sa:
            with patch("diplomacy_bot.modules.stats.auto_upgrade_gold") as au:
                r = stats.run_stat_automation("tok", cfg)
        self.assertEqual(r, {"passive": [], "upgrades": []})
        sa.assert_not_called()  # throttle → hiç upgrade yoluna girmedi
        au.assert_not_called()

    def test_throttle_expired_allows_upgrade(self):
        """10dk geçtiyse throttle kalkar."""
        stats._LAST_UPGRADE_429_AT = time.time() - 601
        cfg = AccountConfig("t", stat_auto_enabled=True)
        with patch("diplomacy_bot.modules.stats.spend_available", return_value=[]):
            with patch("diplomacy_bot.modules.stats.auto_upgrade_gold", return_value=[]):
                r = stats.run_stat_automation("tok", cfg)
        self.assertEqual(r["upgrades"], [])

    def test_stat_auto_disabled_skips(self):
        cfg = AccountConfig("t", stat_auto_enabled=False)
        r = stats.run_stat_automation("tok", cfg)
        self.assertEqual(r, {"passive": [], "upgrades": []})


if __name__ == "__main__":
    unittest.main()
