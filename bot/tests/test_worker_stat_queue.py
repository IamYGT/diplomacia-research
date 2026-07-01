"""Worker stat queue tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WorkerStatQueueTests(unittest.TestCase):
    def test_worker_stat_queue_ticks_accounts(self):
        from diplomacy_bot.jobs.worker_stat_queue import run_worker_stat_queue_once

        acc1 = SimpleNamespace(name="w1")
        acc2 = SimpleNamespace(name="w2")
        with (
            patch("diplomacy_bot.stat_queue.accounts_for_stat_queue", return_value=[acc1, acc2]),
            patch("diplomacy_bot.stat_queue.tick_stat_queue", side_effect=[{"upgrades": [1]}, None]) as tick,
        ):
            changed, attempted = run_worker_stat_queue_once()

        self.assertEqual((changed, attempted), (1, 2))
        self.assertEqual(tick.call_count, 2)

    def test_worker_stat_queue_continues_after_error(self):
        from diplomacy_bot.jobs.worker_stat_queue import run_worker_stat_queue_once

        acc1 = SimpleNamespace(name="w1")
        acc2 = SimpleNamespace(name="w2")

        def tick(acc):
            if acc.name == "w1":
                raise RuntimeError("boom")
            return {"ok": True}

        with (
            patch("diplomacy_bot.stat_queue.accounts_for_stat_queue", return_value=[acc1, acc2]),
            patch("diplomacy_bot.stat_queue.tick_stat_queue", side_effect=tick),
        ):
            changed, attempted = run_worker_stat_queue_once()

        self.assertEqual((changed, attempted), (1, 2))


if __name__ == "__main__":
    unittest.main()
