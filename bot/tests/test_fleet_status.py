"""Filo durum ve inbox testleri."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _TgObj:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _TgButton:
    def __init__(self, text, callback_data=None, **kwargs):
        self.text = text
        self.callback_data = callback_data
        self.kwargs = kwargs


class _TgMarkup:
    def __init__(self, inline_keyboard):
        self.inline_keyboard = inline_keyboard


if "telegram" not in sys.modules:
    telegram_stub = ModuleType("telegram")
    sys.modules["telegram"] = telegram_stub
telegram_stub = sys.modules["telegram"]
telegram_stub.Bot = getattr(telegram_stub, "Bot", _TgObj)
telegram_stub.BotCommand = getattr(telegram_stub, "BotCommand", _TgObj)
telegram_stub.InlineKeyboardButton = getattr(telegram_stub, "InlineKeyboardButton", _TgButton)
telegram_stub.InlineKeyboardMarkup = getattr(telegram_stub, "InlineKeyboardMarkup", _TgMarkup)
telegram_stub.KeyboardButton = getattr(telegram_stub, "KeyboardButton", _TgObj)
telegram_stub.MenuButtonCommands = getattr(telegram_stub, "MenuButtonCommands", _TgObj)
telegram_stub.ReplyKeyboardMarkup = getattr(telegram_stub, "ReplyKeyboardMarkup", _TgObj)
telegram_stub.Update = getattr(telegram_stub, "Update", _TgObj)
if "telegram.ext" not in sys.modules:
    ext_stub = ModuleType("telegram.ext")
    sys.modules["telegram.ext"] = ext_stub
ext_stub = sys.modules["telegram.ext"]
ext_stub.Application = getattr(ext_stub, "Application", MagicMock)
ext_stub.CallbackQueryHandler = getattr(ext_stub, "CallbackQueryHandler", MagicMock)
ext_stub.CommandHandler = getattr(ext_stub, "CommandHandler", MagicMock)
ext_stub.ContextTypes = getattr(ext_stub, "ContextTypes", MagicMock)
ext_stub.MessageHandler = getattr(ext_stub, "MessageHandler", MagicMock)
ext_stub.filters = getattr(ext_stub, "filters", MagicMock)
if "telegram.constants" not in sys.modules:
    constants_stub = ModuleType("telegram.constants")
    sys.modules["telegram.constants"] = constants_stub
constants_stub = sys.modules["telegram.constants"]
constants_stub.ChatAction = getattr(constants_stub, "ChatAction", MagicMock)
if "telegram.error" not in sys.modules:
    error_stub = ModuleType("telegram.error")
    sys.modules["telegram.error"] = error_stub
error_stub = sys.modules["telegram.error"]
error_stub.BadRequest = getattr(error_stub, "BadRequest", Exception)
error_stub.Conflict = getattr(error_stub, "Conflict", Exception)

from diplomacy_bot.fleet_status import (
    compute_fleet_next_steps,
    format_autopilot_target_line,
    format_factory_capacity_line,
    format_fleet_ops_status,
    format_next_steps_footer,
)
from diplomacy_bot.fleet_autopilot_policy import FleetAutopilotPolicy
from diplomacy_bot.fleet_capabilities import format_fleet_capability_line
from diplomacy_bot.telegram_ui import format_fleet_html
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
    def test_empty_status_uses_real_token_inbox_path(self):
        with patch("diplomacy_bot.fleet_status.scoped_list_accounts", return_value=[]):
            html = format_fleet_ops_status(515491882)
        self.assertIn("data/token_inbox/u515491882_01.jwt", html)
        self.assertIn("/fleetstart", html)
        self.assertNotIn("{uid}", html)

    def test_next_steps_suggest_factory_when_not_fixed(self):
        acc = _acc()
        cfg = MagicMock(work_mode="foreign", preferred_factory_id=None, role="hybrid")
        with (
            patch("diplomacy_bot.fleet_status.scoped_list_accounts", return_value=[acc]),
            patch("diplomacy_bot.fleet_command.resolve_operator_factory", return_value=("fid-1", "Hürmüz", "")),
            patch("diplomacy_bot.fleet_status.get_config", return_value=cfg),
            patch("diplomacy_bot.token_watch.list_fresh_inbox_import_candidates", return_value=[]),
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

    def test_autopilot_target_line_shows_policy_and_pending_tokens(self):
        policy = FleetAutopilotPolicy(province="Hürmüz", role="hybrid", vote=True)
        with (
            patch("diplomacy_bot.fleet_autopilot_policy.load_fleet_autopilot_policy", return_value=policy),
            patch("diplomacy_bot.token_watch.list_fresh_inbox_import_candidates", return_value=[("u99_01", "tok")]),
        ):
            line = format_autopilot_target_line(99)
        self.assertIn("Başlat hedefi", line)
        self.assertIn("Hürmüz", line)
        self.assertIn("oy", line)
        self.assertIn("1 token bekliyor", line)

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
            patch("diplomacy_bot.fleet_blocker_summary.format_fleet_blocker_summary", return_value="🧯 Darboğaz: 1 cooldown"),
            patch("diplomacy_bot.fleet_metrics.format_fleet_metrics_line", return_value=""),
            patch("diplomacy_bot.fleet_status.format_autopilot_target_line", return_value="🎯 Başlat hedefi: Hürmüz"),
            patch("diplomacy_bot.fleet_status.format_next_steps_footer", return_value=""),
            patch("diplomacy_bot.mission_store.get_active_mission", return_value=rt),
        ):
            html = format_fleet_ops_status(99)
        self.assertIn("travel_to_province:waiting", html)
        self.assertIn("Otonomi audit", html)
        self.assertIn("Darboğaz", html)
        self.assertIn("Başlat hedefi", html)
        self.assertIn("Gelişmiş kabiliyet", html)

    def test_status_limit_allows_main_plus_twenty_workers(self):
        accs = [_acc("main")] + [_acc(f"w{i:02d}") for i in range(20)]
        cfg = MagicMock(role="hybrid", work_mode="fixed", preferred_factory_id="factory-uuid")
        with (
            patch("diplomacy_bot.fleet_status.scoped_list_accounts", return_value=accs),
            patch("diplomacy_bot.fleet_status.get_main_account_name", return_value="main"),
            patch("diplomacy_bot.fleet_command.resolve_operator_factory", return_value=("factory-uuid", "Hürmüz", "")),
            patch("diplomacy_bot.fleet_status.get_config", return_value=cfg),
            patch("diplomacy_bot.fleet_status.resolve_display_balance", return_value=MagicMock(format=lambda: "1")),
            patch("diplomacy_bot.fleet_status.format_factory_capacity_line", return_value=""),
            patch("diplomacy_bot.fleet_status.format_next_steps_footer", return_value=""),
        ):
            html = format_fleet_ops_status(99)

        self.assertIn("21/21 hesap", html)
        self.assertIn("<code>w19</code>", html)
        self.assertNotIn("+1 hesap", html)

    def test_capability_line_surfaces_unknown_advanced_routes(self):
        line = format_fleet_capability_line()
        self.assertIn("fabrika çalışma", line)
        self.assertIn("saatlik antrenman saldırı", line)
        self.assertIn("çalışma izni", line)
        self.assertIn("endpoint keşfi bekliyor", line)

    def test_fleet_panel_copy_prioritizes_simple_flow(self):
        acc = _acc()
        cfg = MagicMock(role="hybrid", work_mode="fixed")
        with patch("diplomacy_bot.telegram_ui.get_config", return_value=cfg):
            html = format_fleet_html("u99_worker", [acc])
        self.assertIn("Önerilen akış", html)
        self.assertIn("▶️ Başlat", html)
        self.assertIn("⚙️ İşlemler", html)


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

    def test_same_slot_existing_player_remains_candidate_for_refresh(self):
        from diplomacy_bot.token_watch import list_inbox_import_candidates

        tok = "eyJhbGciOiJIUzI1NiJ9.eyJpZCI6InAxIn0.sig"
        with (
            patch("diplomacy_bot.token_watch.scan_token_inbox", return_value={"u77_01": tok}),
            patch("diplomacy_bot.auth.scoped_list_accounts", return_value=[_acc("u77_01", uid=77)]),
            patch("diplomacy_bot.token_watch.player_id_from_token", return_value="p1"),
        ):
            got = list_inbox_import_candidates(77)

        self.assertEqual(got, [("u77_01", tok)])

    def test_duplicate_player_in_other_slot_remains_candidate_for_terminal_error(self):
        from diplomacy_bot.token_watch import list_inbox_import_candidates

        tok = "eyJhbGciOiJIUzI1NiJ9.eyJpZCI6InAxIn0.sig"
        with (
            patch("diplomacy_bot.token_watch.scan_token_inbox", return_value={"u77_02": tok}),
            patch("diplomacy_bot.auth.scoped_list_accounts", return_value=[_acc("u77_01", uid=77)]),
            patch("diplomacy_bot.token_watch.player_id_from_token", return_value="p1"),
        ):
            got = list_inbox_import_candidates(77)

        self.assertEqual(got, [("u77_02", tok)])

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
