#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.modules import travel, war
from diplomacy_bot.war_resolver import format_war_sides, parse_war_reference, resolve_war_from_reference


class TravelModuleTests(unittest.TestCase):
    def test_is_traveling_true(self):
        def api(m, p, t, body=None, delay=0):
            return 200, {"traveling": True, "arrived": False, "remaining_ms": 5000}

        self.assertTrue(travel.is_traveling("tok", _api=api))

    def test_ensure_already_there(self):
        from unittest.mock import patch

        prof = type("P", (), {"province_name": "Bükreş"})()

        def api(m, p, t, body=None, delay=0):
            return 404, {}

        with patch("diplomacy_bot.modules.travel.get_profile", return_value=prof):
            r = travel.ensure_in_province("tok", "Bükreş", _api=api)
            self.assertTrue(r["ok"])
            self.assertEqual(r.get("skipped"), "already_there")

    def test_start_travel_falls_back_to_province_id(self):
        calls = []

        def api(m, p, t, body=None, delay=0):
            calls.append((m, p, body))
            if p == "/provinces/all":
                return 200, {"provinces": [{"id": 42, "name": "Hürmüz"}]}
            if p == "/provinces/travel/start" and body and body.get("province_id") == 42:
                return 200, {"ok": True}
            if p == "/provinces/travel/start":
                return 400, {"error": "province_id required"}
            return 404, {}

        r = travel.start_travel("tok", "Hürmüz", _api=api)
        self.assertTrue(r["ok"])
        self.assertTrue(any((body or {}).get("province_id") == 42 for _, _, body in calls))


class WarResolverTests(unittest.TestCase):
    def test_parse_url(self):
        ref = parse_war_reference("https://diplomacia.com.tr/wars/war/329")
        self.assertEqual(ref["url_number"], "329")

    def test_parse_text(self):
        ref = parse_war_reference("sırbistan savaşı")
        self.assertEqual(ref["text_query"], "sırbistan savaşı")

    def test_resolve_by_text(self):
        wars = [
            {
                "id": "uuid-1",
                "attacker_name": "Sırbistan",
                "defender_name": "Hırvatistan",
                "attacker_province": "Belgrad",
                "defender_province": "Zagreb",
            }
        ]
        ref = parse_war_reference("sırbistan")
        w = resolve_war_from_reference(wars, ref)
        self.assertEqual(w["id"], "uuid-1")

    def test_format_sides(self):
        text = format_war_sides(
            {"attacker_name": "A", "defender_name": "D", "attacker_province": "X", "defender_province": "Y"},
            index=329,
        )
        self.assertIn("Saldırgan", text)
        self.assertIn("Savunmacı", text)


class WarCooldownTests(unittest.TestCase):
    def test_war_cooldown_skip(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/auto/status":
                return 200, {"next_war_in_ms": 600_000}
            return 200, {}

        cfg = AccountConfig(account_name="a", war_enabled=True)
        r = war.try_contribute("tok", cfg, _api=api)
        self.assertEqual(r.get("skipped"), "war_cooldown")

    def test_contribute_first_war(self):
        def api(m, p, t, body=None, delay=0):
            if p == "/auto/status":
                return 200, {"next_war_in_ms": 0}
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
