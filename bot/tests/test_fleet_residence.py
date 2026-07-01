"""Filo bölge (ikamet/oy/vize) testleri."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from diplomacy_bot.fleet_residence import (
    _pick_vote_targets,
    cast_election_vote,
    set_residence,
)
from diplomacy_bot.store import Account


def _acc() -> Account:
    return Account(
        id=1,
        name="u1_w",
        token="eyJtok",
        player_id="p1",
        username="w",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )


class FleetResidenceTests(unittest.TestCase):
    def test_set_residence_put_success(self):
        calls = []

        def mock_api(method, path, token, body=None, delay=0):
            calls.append(method)
            if method == "PUT":
                return 200, {"residence_province": "Hürmüz"}
            return 400, {"error": "fail"}

        with patch("diplomacy_bot.modules.travel.list_provinces", return_value=[]):
            r = set_residence("tok", "Hürmüz", _api=mock_api)
        self.assertTrue(r["ok"])
        self.assertIn("PUT", calls)

    def test_set_residence_province_id_fallback(self):
        calls = []

        def mock_api(method, path, token, body=None, delay=0):
            calls.append(body)
            if body and body.get("province_id") == 42:
                return 200, {"residence_province": "Hürmüz"}
            return 400, {"error": "fail"}

        with patch(
            "diplomacy_bot.modules.travel.list_provinces",
            return_value=[{"id": 42, "name": "Hürmüz"}],
        ):
            r = set_residence("tok", "Hürmüz", _api=mock_api)
        self.assertTrue(r["ok"])
        self.assertTrue(any(c and c.get("province_id") == 42 for c in calls))

    def test_format_post_aod_footer(self):
        from diplomacy_bot.fleet_status import format_post_aod_footer

        html = format_post_aod_footer()
        self.assertIn("/fleetvote", html)
        self.assertIn("/fleet status", html)

    def test_pick_vote_targets_first_candidate(self):
        data = {
            "elections": [
                {
                    "id": "el-1",
                    "candidates": [{"id": "cand-99", "name": "A"}],
                }
            ]
        }
        eid, cid = _pick_vote_targets(data, None)
        self.assertEqual(eid, "el-1")
        self.assertEqual(cid, "cand-99")

    def test_cast_vote_with_mock(self):
        def mock_api(method, path, token, body=None, delay=0):
            if path == "/elections/active":
                return 200, {"elections": [{"id": "e1", "candidates": [{"id": "c1"}]}]}
            if path == "/elections/vote":
                return 200, {"ok": True}
            return 404, {}

        r = cast_election_vote("tok", _api=mock_api)
        self.assertTrue(r["ok"])

    def test_set_account_residence_already_there(self):
        from diplomacy_bot.fleet_residence import set_account_residence

        with (
            patch("diplomacy_bot.fleet_residence.account_context"),
            patch(
                "diplomacy_bot.fleet_residence.get_residence_info",
                return_value={"ok": True, "residence_province": "Hürmüz"},
            ),
        ):
            r = set_account_residence(_acc(), "Hürmüz")
        self.assertTrue(r.ok)
        self.assertIn("zaten", r.message)


if __name__ == "__main__":
    unittest.main()
