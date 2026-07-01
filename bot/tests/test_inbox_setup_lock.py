"""Fleet inbox setup lock tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class InboxSetupLockTests(unittest.TestCase):
    def test_lock_blocks_second_acquire_and_releases(self):
        from diplomacy_bot import inbox_setup_lock

        with tempfile.TemporaryDirectory() as tmp:
            with patch("diplomacy_bot.inbox_setup_lock._LOCK_DIR", Path(tmp)):
                with inbox_setup_lock.acquire_inbox_setup_lock(42) as first:
                    self.assertTrue(first)
                    with inbox_setup_lock.acquire_inbox_setup_lock(42) as second:
                        self.assertFalse(second)
                with inbox_setup_lock.acquire_inbox_setup_lock(42) as again:
                    self.assertTrue(again)


if __name__ == "__main__":
    unittest.main()
