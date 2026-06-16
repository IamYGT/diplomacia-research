#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import telegram_app


class TelegramAppImportTests(unittest.TestCase):
  """Import/regresyon smoke — PM2 crash loop önleme."""

  def test_module_imports(self):
    self.assertTrue(hasattr(telegram_app, "run"))

  def test_critical_symbols(self):
    for sym in (
        "TELEGRAM_BOT_TOKEN",
        "USER_FACING_ERROR",
        "on_callback",
        "_handle_callback",
        "_callback_toast",
        "_loading_edit",
        "run",
    ):
      self.assertTrue(
          hasattr(telegram_app, sym),
          f"telegram_app.{sym} eksik — import regresyonu",
      )

  def test_callback_toast_farm(self):
    self.assertIn("Farm", telegram_app._callback_toast("action:farm"))

  def test_callback_toast_refresh(self):
    self.assertIn("Güncelleniyor", telegram_app._callback_toast("dash:refresh"))

  def test_user_facing_error_generic(self):
    self.assertNotIn("Exception", telegram_app.USER_FACING_ERROR)
    self.assertIn("/start", telegram_app.USER_FACING_ERROR)


if __name__ == "__main__":
  unittest.main()
