"""AOD setup ve primary_factory otomatik kayıt testleri."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_resolve_operator_factory_auto_persists_primary():
    from diplomacy_bot.fleet_command import resolve_operator_factory

    with (
        patch("diplomacy_bot.fleet_command.get_main_account_name", return_value="ygt"),
        patch("diplomacy_bot.fleet_command.get_account") as ga,
        patch("diplomacy_bot.fleet_command.get_config") as gc,
        patch("diplomacy_bot.fleet_command.game_api") as api,
        patch("diplomacy_bot.fleet_command.update_config_field") as uc,
        patch("diplomacy_bot.fleet_command.lookup_factory_province", return_value="Hürmüz"),
    ):
        ga.return_value = MagicMock(token="tok")
        cfg = MagicMock()
        cfg.primary_factory_id = None
        cfg.preferred_factory_id = None
        gc.return_value = cfg
        api.side_effect = [
            (200, {"working": False}),
            (200, {"factories": [{"id": "auto-factory-uuid", "province_name": "Hürmüz"}]}),
        ]
        fid, prov, err = resolve_operator_factory(515491882)
    assert fid == "auto-factory-uuid"
    assert err == ""
    uc.assert_called_once()
    assert uc.call_args[1]["primary_factory_id"] == "auto-factory-uuid"


def test_run_aod_setup_skips_factory_when_unresolved():
    from diplomacy_bot.fleet_aod_setup import run_aod_setup

    with (
        patch("diplomacy_bot.fleet_aod_setup.bootstrap_fleet") as boot,
        patch(
            "diplomacy_bot.fleet_aod_setup.resolve_operator_factory",
            return_value=(None, None, "UUID yok"),
        ),
        patch("diplomacy_bot.fleet_aod_setup.assign_fleet_to_factory") as assign,
        patch("diplomacy_bot.fleet_aod_setup.travel_fleet") as travel,
        patch("diplomacy_bot.fleet_aod_setup.set_fleet_residence") as residence,
    ):
        from diplomacy_bot.fleet_command import FleetBatchResult

        boot.return_value = FleetBatchResult()
        travel.return_value = FleetBatchResult()
        residence.return_value = FleetBatchResult()
        steps = run_aod_setup(1)
    assign.assert_not_called()
    assert "atlandı" in steps["factory"].results[0].message


def test_format_aod_html_factory_skip_label():
    from diplomacy_bot.fleet_command import FleetBatchResult, FleetOpResult
    from diplomacy_bot.fleet_region_hooks import _format_aod_html

    steps = {
        "bootstrap": FleetBatchResult(total=1, ok=1),
        "factory": FleetBatchResult(),
        "travel": FleetBatchResult(total=1, ok=1),
        "residence": FleetBatchResult(total=1, ok=1),
    }
    steps["factory"].add(FleetOpResult("-", False, "⏭ atlandı — UUID yok"))
    with patch("diplomacy_bot.account_main.get_main_account_name", return_value="ygt"):
        with patch("diplomacy_bot.account_config.get_config") as gc:
            gc.return_value = MagicMock(primary_factory_id=None)
            html = _format_aod_html(steps, 1)
    assert "⏭ atlandı" in html
    assert "Ana fabrika UUID yok" in html
