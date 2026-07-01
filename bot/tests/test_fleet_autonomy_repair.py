#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_autonomy_repair import repair_fleet_autonomy_for_uid


class FleetAutonomyRepairTests(unittest.TestCase):
    def test_repair_skips_main_and_enables_worker_defaults(self):
        main = SimpleNamespace(name="main")
        worker = SimpleNamespace(name="w1")
        with (
            patch("diplomacy_bot.fleet_autonomy_repair.resolve_operator_factory", return_value=("factory-uuid", "Hürmüz", "")),
            patch("diplomacy_bot.fleet_autonomy_repair.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.fleet_autonomy_repair.scoped_list_accounts", return_value=[main, worker]),
            patch("diplomacy_bot.fleet_autonomy_repair.set_autofarm") as set_auto,
            patch("diplomacy_bot.fleet_autonomy_repair.update_config_field") as update_cfg,
        ):
            batch = repair_fleet_autonomy_for_uid(42)

        self.assertEqual((batch.ok, batch.total), (1, 1))
        set_auto.assert_called_once_with("w1", True)
        update_cfg.assert_called_once()
        self.assertEqual(update_cfg.call_args.args[0], "w1")
        kwargs = update_cfg.call_args.kwargs
        self.assertEqual(kwargs["role"], "hybrid")
        self.assertEqual(kwargs["work_mode"], "fixed")
        self.assertEqual(kwargs["preferred_factory_id"], "factory-uuid")
        self.assertTrue(kwargs["stat_auto_enabled"])
        self.assertTrue(kwargs["training_enabled"])
        self.assertTrue(kwargs["craft_pills_when_low"])
        self.assertTrue(kwargs["auto_travel_enabled"])

    def test_repair_reports_missing_factory(self):
        with patch("diplomacy_bot.fleet_autonomy_repair.resolve_operator_factory", return_value=(None, None, "fabrika yok")):
            batch = repair_fleet_autonomy_for_uid(42)

        self.assertEqual((batch.ok, batch.total), (0, 1))
        self.assertIn("fabrika yok", batch.results[0].message)


if __name__ == "__main__":
    unittest.main()
