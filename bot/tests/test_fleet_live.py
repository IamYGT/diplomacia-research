#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_live import FleetLiveState, format_tick_line, farm_to_tick
from diplomacy_bot.farmer import FarmResult
from diplomacy_bot.modules.orchestrator import TickResult
from diplomacy_bot.store import Account


def _acc(name: str = "ygt") -> Account:
    return Account(
        id=1,
        name=name,
        token="t",
        player_id="p",
        username="YGT",
        autofarm=True,
        last_farm_at=0,
        last_balance=1000,
        proxy_id="tor-01",
        proxy_url="",
        status="active",
    )


class FleetLiveTests(unittest.TestCase):
    def test_format_tick_success(self):
        r = TickResult(
            account_name="ygt",
            username="YGT",
            ok=True,
            balance_before=1000,
            balance_after=3400,
            earned_money=2400,
            earned_xp=5,
        )
        line = format_tick_line(_acc(), r)
        self.assertIn("✅", line)
        self.assertIn("2,400", line)

    def test_format_tick_cooldown(self):
        r = TickResult(account_name="ygt", error="work cooldown", ok=False)
        line = format_tick_line(_acc(), r)
        self.assertIn("⏳", line)
        self.assertIn("cooldown", line)

    def test_farm_to_tick(self):
        fr = FarmResult(
            account_name="a",
            username="u",
            ok=True,
            balance_before=1,
            balance_after=2,
            earned_money=1,
            earned_xp=0,
            earned_diamonds=0,
        )
        t = farm_to_tick(fr)
        self.assertEqual(t.earned_money, 1)

    def test_live_state_text_shows_queue(self):
        st = FleetLiveState([_acc("a"), _acc("b")])
        self.assertIn("sırada", st.text())
        st.status["a"] = "✅ a [Farm] +100₺ → 1,100₺"
        self.assertIn("1/2 bitti", st.text())


if __name__ == "__main__":
    unittest.main()
