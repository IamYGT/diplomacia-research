#!/usr/bin/env python3
"""factory_service birim testleri — mock API ile."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import factory_service
from diplomacy_bot.game_api import Profile


def _profile(**kw) -> Profile:
    defaults = dict(
        player_id="p1",
        username="test",
        balance=1000,
        diamonds=10,
        xp=100,
        level=4,
        health=100,
        health_pills=5,
        onboarding_step=None,
        province_name="TestProvince",
    )
    defaults.update(kw)
    return Profile(**defaults)


class MockApi:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, dict]]):
        self.responses = responses
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method: str, path: str, token: str, body=None, delay=0):
        self.calls.append((method, path, body))
        key = (method, path)
        if key in self.responses:
            return self.responses[key]
        return 404, {"error": "not found"}


class FactoryServiceTests(unittest.TestCase):
    def test_factory_in_province_prefers_current(self):
        mock = MockApi(
            {
                ("GET", "/factories/my"): (
                    200,
                    {
                        "factories": [
                            {"id": "far", "province_name": "Other"},
                            {"id": "local", "province_name": "TestProvince"},
                        ]
                    },
                ),
            }
        )
        with patch.object(factory_service, "get_profile", return_value=_profile()):
            fid = factory_service.factory_in_province("tok", _api=mock)
        self.assertEqual(fid, "local")

    def test_ensure_factory_builds_when_missing(self):
        mock = MockApi(
            {
                ("GET", "/factories/my"): (200, {"factories": []}),
                ("POST", "/factories/build"): (201, {"factory": {"id": "new-f"}}),
            }
        )
        with patch.object(factory_service, "get_profile", return_value=_profile()):
            fid = factory_service.ensure_factory("tok", _api=mock)
        self.assertEqual(fid, "new-f")

    def test_prepare_join_rebuilds_on_region_error(self):
        join_n = {"n": 0}

        def api_fn(method, path, token, body=None, delay=0):
            if method == "GET" and path == "/factories/work-status":
                return 200, {"working": False}
            if method == "GET" and path == "/factories/my":
                return 200, {"factories": [{"id": "f1", "province_name": "TestProvince"}]}
            if method == "POST" and path == "/factories/join":
                join_n["n"] += 1
                if join_n["n"] == 1:
                    return 400, {"error": "Farklı bölgedesiniz"}
                return 200, {"message": "joined"}
            if method == "POST" and path == "/factories/build":
                return 201, {"factory": {"id": "f2"}}
            return 200, {}

        with patch.object(factory_service, "get_profile", return_value=_profile()):
            fid = factory_service.prepare_join("tok", "f1", _api=api_fn)
        self.assertEqual(fid, "f2")

    def test_use_pills_skips_at_full_health(self):
        mock = MockApi({})
        with patch.object(factory_service, "get_profile", return_value=_profile(health=100)):
            err = factory_service.use_pills_if_needed("tok", _api=mock)
        self.assertIsNone(err)
        self.assertEqual(mock.calls, [])

    def test_use_pills_returns_error_on_cooldown(self):
        mock = MockApi(
            {("POST", "/auto/use-pills"): (429, {"error": "cooldown", "remaining_ms": 600000})}
        )
        with patch.object(factory_service, "get_profile", return_value=_profile(health=0)):
            err = factory_service.use_pills_if_needed("tok", _api=mock)
        self.assertIsNotNone(err)
        self.assertIn("cooldown", err["error"])
        self.assertEqual(err["cooldown_ms"], 600000)

    def test_run_work_cycle_success(self):
        mock = MockApi(
            {
                ("GET", "/factories/work-status"): (200, {"working": False}),
                ("GET", "/factories/my"): (
                    200,
                    {"factories": [{"id": "f1", "province_name": "TestProvince"}]},
                ),
                ("POST", "/factories/join"): (200, {"message": "ok"}),
                ("POST", "/factories/work"): (200, {"earned": {"money": 2400}}),
            }
        )
        with patch.object(factory_service, "get_profile", return_value=_profile(health=100)):
            result = factory_service.run_work_cycle("tok", _api=mock)
        self.assertTrue(result["ok"])
        self.assertEqual(result["earned"]["money"], 2400)

    def test_run_work_cycle_stops_on_pill_error(self):
        mock = MockApi(
            {
                ("GET", "/factories/work-status"): (200, {"working": False}),
                ("GET", "/factories/my"): (
                    200,
                    {"factories": [{"id": "f1", "province_name": "TestProvince"}]},
                ),
                ("POST", "/factories/join"): (200, {}),
                ("POST", "/auto/use-pills"): (400, {"error": "Hap bekleme süresi"}),
            }
        )
        with patch.object(factory_service, "get_profile", return_value=_profile(health=20)):
            result = factory_service.run_work_cycle("tok", _api=mock)
        self.assertFalse(result["ok"])
        self.assertIn("bekleme", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
