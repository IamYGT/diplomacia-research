#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.version import get_version, get_version_label


class VersionTests(unittest.TestCase):
    def test_version_semver(self):
        v = get_version()
        parts = v.split(".")
        self.assertEqual(len(parts), 3)
        for p in parts:
            self.assertTrue(p.isdigit())

    def test_version_label(self):
        self.assertTrue(get_version_label().startswith("v"))


if __name__ == "__main__":
    unittest.main()
