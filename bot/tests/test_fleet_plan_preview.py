"""Fleet plan preview command tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.domain.fleet_llm_decision import normalize_llm_decision
from diplomacy_bot.fleet_plan_preview import format_fleet_plan_preview_html
from diplomacy_bot.fleet_start_planner import FleetStartPlan


class FleetPlanPreviewTests(unittest.IsolatedAsyncioTestCase):
    def test_format_preview_shows_target_without_starting(self):
        plan = FleetStartPlan("Hürmüz", {"vote": True, "province_vote": True}, source="deepseek")

        html = format_fleet_plan_preview_html(plan)

        self.assertIn("Filo hedef önizleme", html)
        self.assertIn("Hürmüz", html)
        self.assertIn("DeepSeek planı", html)
        self.assertIn("oy", html.lower())
        self.assertIn("/fleetstart Hürmüz vote eyaletoy", html)
        self.assertIn("/fleetregion Hürmüz vote eyaletoy", html)
        self.assertIn("sadece önizleme", html)

    async def test_fleetplan_command_replies_with_preview(self):
        from diplomacy_bot.fleet_plan_preview import cmd_fleetplan

        msg = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=42), effective_message=msg, message=msg)
        context = SimpleNamespace(args=["20", "hesabı", "Hürmüz'e", "çek", "oy", "ver"])
        decision = normalize_llm_decision({"province": "Hürmüz", "vote": True})
        plan = SimpleNamespace(
            province=decision.target.province,
            opts={"vote": decision.target.vote},
            source="deepseek",
            warnings=(),
        )

        with (
            patch("diplomacy_bot.telegram_helpers.bot_allows_user", return_value=True),
            patch("diplomacy_bot.telegram_app._uid", return_value=42),
            patch("diplomacy_bot.fleet_plan_preview.fleet_nav_inline_markup", return_value=None),
            patch("diplomacy_bot.fleet_plan_preview.resolve_fleet_start_plan", return_value=plan) as resolve,
        ):
            await cmd_fleetplan(update, context)

        resolve.assert_called_once_with(42, context.args)
        msg.reply_text.assert_awaited_once()
        html = msg.reply_text.await_args.args[0]
        self.assertIn("Filo hedef önizleme", html)
        self.assertIn("DeepSeek planı", html)


if __name__ == "__main__":
    unittest.main()
