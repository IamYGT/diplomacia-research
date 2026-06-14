#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import tor_pool


class TorPoolTests(unittest.TestCase):
    def test_rotate_success(self):
        fake_out = "250 OK\r\n250 OK\r\n250 closing connection\r\n"
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=fake_out, stderr="")):
            self.assertTrue(tor_pool.rotate_newnym())

    def test_rotate_missing_cookie(self):
        with patch.object(tor_pool, "COOKIE_PATH", Path("/nonexistent/cookie")):
            self.assertFalse(tor_pool.rotate_newnym())

    def test_tor_socks_url(self):
        self.assertIn("9050", tor_pool.tor_socks_url())


if __name__ == "__main__":
    unittest.main()
