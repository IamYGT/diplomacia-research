"""connect_intel ve seyahat fast-path testleri."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from diplomacy_bot.connect_intel import (
    decode_jwt_payload,
    plan_token_connect,
    suggest_new_account_name,
)
from diplomacy_bot.game_api import Profile
from diplomacy_bot.intent_travel_fast import try_travel_fast_path


class ConnectIntelTests(unittest.TestCase):
    def test_decode_jwt_username(self):
        # payload: {"username":"cursor","id":"abc"}
        import base64
        import json

        payload = base64.urlsafe_b64encode(
            json.dumps({"username": "cursor", "id": "pid-1"}).encode()
        ).decode().rstrip("=")
        token = f"eyJhbGciOiJIUzI1NiJ9.{payload}.sig"
        data = decode_jwt_payload(token)
        self.assertEqual(data.get("username"), "cursor")

    def test_suggest_name_from_username(self):
        self.assertEqual(suggest_new_account_name(1, "Y.G.T1"), "ygt1")

    def test_blocks_overwrite_different_player_on_refresh(self):
        prof = Profile(
            player_id="new-pid",
            username="cursor",
            balance=1,
            diamonds=0,
            xp=0,
            level=1,
            health=100,
            health_pills=0,
            onboarding_step=None,
        )
        existing = MagicMock()
        existing.player_id = "old-pid"
        existing.telegram_user_id = 99

        with patch("diplomacy_bot.game_api.get_profile", return_value=prof):
            with patch("diplomacy_bot.connect_intel.get_account", return_value=existing):
                plan = plan_token_connect(
                    "tok",
                    99,
                    pending_refresh="ygt",
                )
        self.assertEqual(plan.action, "reject")
        self.assertIn("/add", plan.message)

    def test_new_player_creates_separate_account(self):
        prof = Profile(
            player_id="pid-cursor",
            username="cursor",
            balance=1,
            diamonds=0,
            xp=0,
            level=1,
            health=100,
            health_pills=0,
            onboarding_step=None,
        )
        acc_ygt = MagicMock()
        acc_ygt.name = "ygt"
        acc_ygt.player_id = "pid-ygt"

        with patch("diplomacy_bot.game_api.get_profile", return_value=prof):
            with patch(
                "diplomacy_bot.connect_intel.scoped_list_accounts",
                return_value=[acc_ygt],
            ):
                with patch("diplomacy_bot.connect_intel.get_account", return_value=None):
                    plan = plan_token_connect(
                        "tok",
                        515491882,
                        pending_connect=True,
                        default_account="ygt",
                    )
        self.assertEqual(plan.action, "save")
        self.assertEqual(plan.account_name, "cursor")


class TravelFastPathTests(unittest.TestCase):
    def test_seyahat_et_alaska(self):
        acc = MagicMock()
        acc.token = "t"
        acc.name = "ygt"

        with patch(
            "diplomacy_bot.travel_commands.run_travel",
            return_value={"ok": True, "started": True, "traveling": True, "destination": "Alaska", "remaining_ms": 120000},
        ):
            r = try_travel_fast_path("Seyahat et alaska", acc)
        self.assertIsNotNone(r)
        self.assertIn("Alaska", r.reply)


if __name__ == "__main__":
    unittest.main()
