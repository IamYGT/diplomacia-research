"""Filo komuta testleri."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from diplomacy_bot.fleet_command import (
    FleetBatchResult,
    assign_account_to_factory,
    bootstrap_fleet,
    format_batch_html,
    resolve_operator_factory,
)
from diplomacy_bot.store import Account


def _acc(name: str = "worker1", uid: int = 42) -> Account:
    return Account(
        id=1,
        name=name,
        token="eyJtok",
        player_id="p1",
        username="w",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=uid,
    )


class FactoryPillBeforeCooldownTests(unittest.TestCase):
    def test_resolve_operator_factory_from_config(self):
        with (
            patch("diplomacy_bot.fleet_command.get_main_account_name", return_value="main1"),
            patch("diplomacy_bot.fleet_command.get_account") as ga,
            patch("diplomacy_bot.fleet_command.get_config") as gc,
            patch("diplomacy_bot.fleet_command.lookup_factory_province", return_value="Hürmüz"),
        ):
            ga.return_value = MagicMock(token="tok")
            cfg = MagicMock()
            cfg.primary_factory_id = "uuid-factory-1234"
            cfg.preferred_factory_id = None
            gc.return_value = cfg
            fid, prov, err = resolve_operator_factory(99)
            self.assertEqual(fid, "uuid-factory-1234")
            self.assertEqual(prov, "Hürmüz")
            self.assertEqual(err, "")

    def test_assign_account_sets_fixed_mode(self):
        with (
            patch("diplomacy_bot.fleet_command.update_config_field") as uc,
            patch("diplomacy_bot.fleet_command.account_context"),
            patch("diplomacy_bot.modules.travel.ensure_in_province", return_value={"ok": True}),
        ):
            r = assign_account_to_factory(_acc(), "uuid-abcd-efgh", province="Hürmüz")
            self.assertTrue(r.ok)
            uc.assert_called_once()
            kwargs = uc.call_args[1]
            self.assertEqual(kwargs["work_mode"], "fixed")
            self.assertEqual(kwargs["preferred_factory_id"], "uuid-abcd-efgh")

    def test_bootstrap_empty_accounts(self):
        with patch("diplomacy_bot.fleet_command.scoped_list_accounts", return_value=[]):
            batch = bootstrap_fleet(1)
            self.assertEqual(batch.total, 1)
            self.assertFalse(batch.results[0].ok)

    def test_format_batch_html(self):
        batch = FleetBatchResult(total=1, ok=1)
        batch.add(type("R", (), {"account_name": "a", "ok": True, "message": "ok"})())
        html = format_batch_html("Test", batch)
        self.assertIn("Test", html)
        self.assertIn("a", html)


class FactoryPillBeforeCooldownTests(unittest.TestCase):
    def test_use_pills_ok_on_work_cooldown(self):
        from diplomacy_bot.account_config import AccountConfig
        from diplomacy_bot.modules import factory as factory_mod

        cfg = AccountConfig(account_name="x", work_mode="fixed", preferred_factory_id="fid1")

        def mock_api(method, path, token, body=None, delay=0):
            if path == "/auto/status":
                return 200, {"next_work_in_ms": 5000, "pill_cooldown_ms": 0}
            if path == "/auto/use-pills":
                return 200, {"ok": True}
            if path == "/factories/work-status":
                return 200, {"working": False}
            return 404, {}

        with patch("diplomacy_bot.health_sync.work_health", return_value=50):
            r = factory_mod.run_work_cycle("tok", cfg, _api=mock_api)
        self.assertTrue(r.get("used_pills"))
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("error"), "work cooldown")


if __name__ == "__main__":
    unittest.main()
