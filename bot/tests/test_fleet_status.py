"""Filo durum ve inbox testleri."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if "telegram" not in sys.modules:
    telegram_stub = ModuleType("telegram")
    telegram_stub.InlineKeyboardButton = MagicMock
    telegram_stub.InlineKeyboardMarkup = MagicMock
    sys.modules["telegram"] = telegram_stub

from diplomacy_bot.fleet_status import (
    compute_fleet_next_steps,
    format_factory_capacity_line,
    format_fleet_ops_status,
    format_next_steps_footer,
)
from diplomacy_bot.fleet_capabilities import format_fleet_capability_line
from diplomacy_bot.store import Account


def _acc(name: str = "u99_worker", uid: int = 99) -> Account:
    return Account(
        id=1,
        name=name,
        token="eyJtok",
        player_id="p1",
        username="w",
        autofarm=False,
        last_farm_at=0.0,
        last_balance=1000,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=uid,
    )


class FleetStatusTests(unittest.TestCase):
    def test_next_steps_suggest_factory_when_not_fixed(self):
        acc = _acc()
        cfg = MagicMock(work_mode="foreign", preferred_factory_id=None, role="hybrid")
        with (
            patch("diplomacy_bot.fleet_status.scoped_list_accounts", return_value=[acc]),
            patch("diplomacy_bot.fleet_command.resolve_operator_factory", return_value=("fid-1", "Hürmüz", "")),
            patch("diplomacy_bot.fleet_status.get_config", return_value=cfg),
            patch("diplomacy_bot.token_watch.list_inbox_import_candidates", return_value=[]),
        ):
            steps = compute_fleet_next_steps(99)
        self.assertTrue(any("fleetfactory" in s for s in steps))

    def test_capacity_warning_when_over_workers(self):
        with (
            patch("diplomacy_bot.fleet_status.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.fleet_status.get_account", return_value=MagicMock(token="tok")),
            patch(
                "diplomacy_bot.fleet_status._fetch_factory_worker_stats",
                return_value={"workers": 2, "capacity": None},
            ),
            patch("diplomacy_bot.fleet_status.count_fleet_on_factory", return_value=8),
        ):
            line = format_factory_capacity_line(99, "fid-1")
        self.assertIn("🟡", line)

    def test_footer_includes_steps(self):
        with patch("diplomacy_bot.fleet_status.compute_fleet_next_steps", return_value=["<code>/fleetinbox</code>"]):
            footer = format_next_steps_footer(1)
        self.assertIn("Sonraki adım", footer)

    def test_status_includes_active_mission_phase(self):
        acc = _acc()
        cfg = MagicMock(role="hybrid", work_mode="fixed", preferred_factory_id="factory-uuid")
        phase = MagicMock()
        phase.phase.value = "travel_to_province"
        rt = MagicMock(phase_index=0, phase_status=MagicMock(value="waiting"))
        rt.plan.phases = [phase]
        with (
            patch("diplomacy_bot.fleet_status.scoped_list_accounts", return_value=[acc]),
            patch("diplomacy_bot.fleet_command.resolve_operator_factory", return_value=("factory-uuid", "Hürmüz", "")),
            patch("diplomacy_bot.fleet_status.get_config", return_value=cfg),
            patch("diplomacy_bot.fleet_status.resolve_display_balance", return_value=MagicMock(format=lambda: "1,000")),
            patch("diplomacy_bot.fleet_status.format_factory_capacity_line", return_value=""),
            patch("diplomacy_bot.fleet_metrics.format_fleet_metrics_line", return_value=""),
            patch("diplomacy_bot.fleet_status.format_next_steps_footer", return_value=""),
            patch("diplomacy_bot.mission_store.get_active_mission", return_value=rt),
        ):
            html = format_fleet_ops_status(99)
        self.assertIn("travel_to_province:waiting", html)
        self.assertIn("Otonomi audit", html)
        self.assertIn("Gelişmiş kabiliyet", html)

    def test_capability_line_surfaces_unknown_advanced_routes(self):
        line = format_fleet_capability_line()
        self.assertIn("çalışma izni", line)
        self.assertIn("endpoint keşfi bekliyor", line)


class TokenInboxFleetTests(unittest.TestCase):
    def test_list_inbox_import_candidates_uid_prefix(self):
        from diplomacy_bot.token_watch import list_inbox_import_candidates

        tok = "eyJhbGciOiJIUzI1NiJ9.eyJpZCI6InAxMjMifQ.sig"
        with (
            patch("diplomacy_bot.token_watch.scan_token_inbox", return_value={"u77_alt": tok}),
            patch("diplomacy_bot.auth.scoped_list_accounts", return_value=[]),
            patch("diplomacy_bot.token_watch.player_id_from_token", return_value="p123"),
        ):
            got = list_inbox_import_candidates(77)
        self.assertEqual(got, [("u77_alt", tok)])

    def test_rejects_other_uid_inbox_files(self):
        from diplomacy_bot.token_watch import list_inbox_import_candidates

        with (
            patch("diplomacy_bot.token_watch.scan_token_inbox", return_value={"u99_x": "eyJt"}),
            patch("diplomacy_bot.auth.scoped_list_accounts", return_value=[]),
            patch("diplomacy_bot.token_watch.player_id_from_token", return_value="p1"),
        ):
            self.assertEqual(list_inbox_import_candidates(88), [])


if __name__ == "__main__":
    unittest.main()
