"""JWT meta ve token yenileme kararı testleri."""

from __future__ import annotations

import base64
import json
import time
import unittest


def _fake_jwt(*, exp_offset: int, player_id: str = "pid1") -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "exp": int(time.time()) + exp_offset,
                "iat": int(time.time()),
                "id": player_id,
            }
        ).encode()
    ).rstrip(b"=").decode()
    return f"eyJ{header[3:]}.{payload}.signature"


class JwtMetaTests(unittest.TestCase):
    def test_expiring_soon_within_lead(self):
        from diplomacy_bot.jwt_meta import is_expiring_soon

        tok = _fake_jwt(exp_offset=3600)
        self.assertTrue(is_expiring_soon(tok, lead_sec=7200))

    def test_not_expiring_soon_far_future(self):
        from diplomacy_bot.jwt_meta import is_expiring_soon

        tok = _fake_jwt(exp_offset=500_000)
        self.assertFalse(is_expiring_soon(tok, lead_sec=259_200))

    def test_player_id_from_token(self):
        from diplomacy_bot.jwt_meta import player_id_from_token

        tok = _fake_jwt(exp_offset=10_000, player_id="abc99")
        self.assertEqual(player_id_from_token(tok), "abc99")

    def test_format_expiry_human_days(self):
        from diplomacy_bot.jwt_meta import format_expiry_human

        tok = _fake_jwt(exp_offset=200_000)
        self.assertIn("gün", format_expiry_human(tok))


class TokenWatchTests(unittest.TestCase):
    def test_pick_inbox_by_account_name(self):
        from diplomacy_bot.token_watch import pick_inbox_token

        tok = _fake_jwt(exp_offset=99_999, player_id="p42")
        inbox = {"ygt": tok}
        got = pick_inbox_token("ygt", "p42", inbox)
        self.assertEqual(got, tok)

    def test_rejects_wrong_player(self):
        from diplomacy_bot.token_watch import pick_inbox_token

        tok = _fake_jwt(exp_offset=99_999, player_id="other")
        inbox = {"ygt": tok}
        self.assertIsNone(pick_inbox_token("ygt", "p42", inbox))


class ShouldRefreshTests(unittest.TestCase):
    def test_should_refresh_when_expiring(self):
        from diplomacy_bot.token_refresh_service import should_refresh_account
        from diplomacy_bot.store import Account

        acc = Account(
            id=1,
            name="t1",
            token=_fake_jwt(exp_offset=1000),
            player_id="p1",
            username="u",
            autofarm=False,
            last_farm_at=0.0,
            last_balance=0,
            proxy_id="direct",
            proxy_url="",
            status="idle",
            telegram_user_id=1,
        )
        self.assertTrue(should_refresh_account(acc, lead_sec=7200))

    def test_skip_when_auto_token_refresh_off(self):
        from diplomacy_bot.account_config import update_config_field
        from diplomacy_bot.token_refresh_service import should_refresh_account
        from diplomacy_bot.store import Account

        acc = Account(
            id=1,
            name="off_acc",
            token=_fake_jwt(exp_offset=100),
            player_id="p1",
            username="u",
            autofarm=False,
            last_farm_at=0.0,
            last_balance=0,
            proxy_id="direct",
            proxy_url="",
            status="idle",
            telegram_user_id=1,
        )
        update_config_field("off_acc", auto_token_refresh=False)
        self.assertFalse(should_refresh_account(acc, lead_sec=999_999))


class ApiLoginRefreshTests(unittest.TestCase):
    def test_api_login_refresh_applies_token(self):
        from unittest.mock import MagicMock, patch

        from diplomacy_bot.account_credentials import save_login
        from diplomacy_bot.game_api import Profile
        from diplomacy_bot.store import Account
        from diplomacy_bot.token_refresh_service import _try_sources_for_account

        old_tok = _fake_jwt(exp_offset=100, player_id="p99")
        new_tok = _fake_jwt(exp_offset=500_000, player_id="p99")
        acc = Account(
            id=1,
            name="api_acc",
            token=old_tok,
            player_id="p99",
            username="tester",
            autofarm=False,
            last_farm_at=0.0,
            last_balance=0,
            proxy_id="direct",
            proxy_url="",
            status="idle",
            telegram_user_id=1,
        )
        save_login("api_acc", "a@b.com", "secret")

        prof = Profile(
            player_id="p99",
            username="tester",
            balance=1,
            diamonds=0,
            xp=0,
            level=1,
            health=100,
            health_pills=0,
            onboarding_step=None,
        )

        with (
            patch("diplomacy_bot.token_refresh_service.login_for_token", return_value=(new_tok, "")),
            patch("diplomacy_bot.token_refresh_service._validate_and_apply") as mock_apply,
        ):
            mock_apply.return_value = MagicMock(ok=True, account_name="api_acc", source="api_login")
            res = _try_sources_for_account(acc, inbox={}, legacy_token=None)
            self.assertIsNotNone(res)
            self.assertTrue(res.ok)
            mock_apply.assert_called_once_with(acc, new_tok, "api_login")


class CoachTokenLineTests(unittest.TestCase):
    def test_coach_shows_token_remaining(self):
        from diplomacy_bot.dashboard_coach import format_coach_dashboard
        from diplomacy_bot.store import Account

        acc = Account(
            id=1,
            name="coach1",
            token=_fake_jwt(exp_offset=200_000),
            player_id="p1",
            username="u",
            autofarm=True,
            last_farm_at=0.0,
            last_balance=0,
            proxy_id="direct",
            proxy_url="",
            status="idle",
            telegram_user_id=0,
        )
        snap = {
            "username": "u",
            "level": 5,
            "province": "Ankara",
            "balance": 100,
            "diamonds": 0,
            "pills": 1,
            "health": 80,
            "autofarm": True,
        }
        html_out = format_coach_dashboard(acc, snap)
        self.assertIn("Token kalan", html_out)


if __name__ == "__main__":
    unittest.main()
