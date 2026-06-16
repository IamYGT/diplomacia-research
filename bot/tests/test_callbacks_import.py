#!/usr/bin/env python3
"""Split sonrası import/acyclic regresyon — callbacks + helpers + app."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import callbacks, telegram_app, telegram_helpers


class SplitImportTests(unittest.TestCase):
    def test_callbacks_handle_callback_exists(self):
        self.assertTrue(callable(getattr(callbacks, "handle_callback", None)))

    def test_helpers_user_facing_error(self):
        self.assertIn("/start", telegram_helpers.USER_FACING_ERROR)

    def test_app_reexports_handle_callback(self):
        """test_telegram_app_import.py geri-uyumu: app._handle_callback = callbacks.handle_callback."""
        self.assertTrue(hasattr(telegram_app, "_handle_callback"))
        self.assertIs(telegram_app._handle_callback, callbacks.handle_callback)

    def test_callbacks_no_top_level_app_import(self):
        """callbacks top-level telegram_app import etmemeli (cycle).

        callbacks→app bağımlılığı yalnızca handle_callback gövdesi içinde lazy
        (runtime) olmalı; top-level import circular olurdu.
        """
        for line in inspect.getsource(callbacks).splitlines():
            stripped = line.lstrip()
            is_top_level = not (line.startswith(" ") or line.startswith("\t"))
            if not is_top_level:
                continue
            for bad in ("from . import telegram_app", "import telegram_app", "from .telegram_app"):
                self.assertFalse(
                    stripped.startswith(bad),
                    f"callbacks top-level app import (cycle riski): {line!r}",
                )

    def test_helpers_no_app_import(self):
        """helpers asla app/callbacks import etmemeli (acyclic kök kısıtı)."""
        for line in inspect.getsource(telegram_helpers).splitlines():
            stripped = line.lstrip()
            if not (stripped.startswith("from ") or stripped.startswith("import ")):
                continue  # docstring/yorum satırlarını atla
            for bad in ("telegram_app", ".callbacks", "import callbacks"):
                self.assertNotIn(
                    bad,
                    stripped,
                    f"helpers app/callbacks import etti (acyclik ihlali): {line!r}",
                )


if __name__ == "__main__":
    unittest.main()
