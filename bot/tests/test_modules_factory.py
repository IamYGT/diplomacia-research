#!/usr/bin/env python3
"""modules.factory — yabancı/sabit fabrika modları."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.game_api import Profile
from diplomacy_bot.modules import factory as factory_mod


def _profile(**kw) -> Profile:
    defaults = dict(
        player_id="p1",
        username="test",
        balance=1000,
        diamonds=5000,
        xp=100,
        level=4,
        health=100,
        health_pills=5,
        onboarding_step=None,
        province_name="Bükreş",
    )
    defaults.update(kw)
    return Profile(**defaults)


class MockApi:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, dict]]):
        self.responses = responses
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method: str, path: str, token: str, body=None, delay=0):
        self.calls.append((method, path, body))
        key = (method, path.split("?")[0] if "?" in path else path)
        for k, v in self.responses.items():
            if k[0] == method and path.startswith(k[1]):
                return v
        if key in self.responses:
            return self.responses[key]
        return 404, {"error": "not found"}


class FactoryModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        factory_mod.clear_factory_cache()
    def test_fixed_mode_uses_preferred_id_no_build(self):
        cfg = AccountConfig(
            account_name="a1",
            work_mode="fixed",
            preferred_factory_id="foreign-fab-99",
            allow_auto_build=False,
        )
        mock = MockApi(
            {
                ("GET", "/factories/work-status"): (200, {"working": False}),
                ("GET", "/auto/status"): (200, {"next_work_in_ms": 0}),
                ("POST", "/factories/join"): (200, {"ok": True}),
                ("POST", "/factories/work"): (200, {"earned": {"money": 2400, "diamonds": 20}}),
            }
        )
        with patch.object(factory_mod, "get_profile", return_value=_profile()):
            r = factory_mod.run_work_cycle("tok", cfg, _api=mock)
        self.assertTrue(r["ok"])
        join_calls = [c for c in mock.calls if c[0] == "POST" and c[1] == "/factories/join"]
        self.assertEqual(join_calls[0][2], {"factory_id": "foreign-fab-99"})
        build_calls = [c for c in mock.calls if c[1] == "/factories/build"]
        self.assertEqual(build_calls, [])

    def test_own_mode_no_build_when_missing(self):
        cfg = AccountConfig(account_name="a1", work_mode="own", allow_auto_build=False)
        mock = MockApi(
            {
                ("GET", "/factories/my"): (200, {"factories": []}),
                ("GET", "/auto/status"): (200, {"next_work_in_ms": 0}),
            }
        )
        with patch.object(factory_mod, "get_profile", return_value=_profile()):
            fid, err = factory_mod.resolve_factory_id("tok", cfg, _api=mock)
        self.assertIsNone(fid)
        self.assertIn("fabrika", (err or "").lower())

    def test_foreign_picks_best_elmas(self):
        cfg = AccountConfig(account_name="a1", work_mode="foreign")
        mock = MockApi(
            {
                ("GET", "/factories/region"): (
                    200,
                    {
                        "factories": [
                            {"id": "gold1", "type": "altin", "level": 50, "salary_rate": 90},
                            {"id": "dia1", "type": "elmas", "level": 80, "salary_rate": 87},
                        ]
                    },
                ),
            }
        )
        with patch.object(factory_mod, "get_profile", return_value=_profile()):
            fid, err = factory_mod.resolve_factory_id("tok", cfg, _api=mock)
        self.assertEqual(fid, "dia1")
        self.assertIsNone(err)

    def test_run_work_cycle_skips_join_when_already_working(self):
        cfg = AccountConfig(account_name="a1", work_mode="foreign")
        mock = MockApi(
            {
                ("GET", "/auto/status"): (200, {"next_work_in_ms": 0, "health": 100}),
                ("GET", "/factories/work-status"): (200, {"working": True, "factory_id": "fab-1"}),
                ("POST", "/factories/work"): (200, {"earned": {"money": 100, "xp": 1}}),
            }
        )
        with patch.object(factory_mod, "get_profile", return_value=_profile()):
            r = factory_mod.run_work_cycle("tok", cfg, _api=mock)
        self.assertTrue(r["ok"])
        join_calls = [c for c in mock.calls if c[1] == "/factories/join"]
        region_calls = [c for c in mock.calls if c[1].startswith("/factories/region")]
        self.assertEqual(join_calls, [])
        self.assertEqual(region_calls, [])


if __name__ == "__main__":
    unittest.main()
