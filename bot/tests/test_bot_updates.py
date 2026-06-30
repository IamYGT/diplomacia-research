#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.bot_updates import (
    format_release_block,
    format_updates_html,
    list_releases,
    release_for_version,
)
from diplomacy_bot.version import get_version


class BotUpdatesTests(unittest.TestCase):
    def test_catalog_loads(self):
        releases = list_releases()
        self.assertGreaterEqual(len(releases), 1)

    def test_current_release_exists(self):
        rel = release_for_version(get_version())
        self.assertIsNotNone(rel)
        self.assertEqual(rel.get("version"), get_version())

    def test_format_has_story(self):
        rel = release_for_version(get_version())
        self.assertIsNotNone(rel)
        html_out = format_release_block(rel, current=True)
        self.assertIn(get_version(), html_out)
        self.assertIn(rel.get("title", ""), html_out.replace("&", ""))  # html escaped ok loosely

    def test_format_updates_page(self):
        text = format_updates_html(page=0)
        self.assertIn("güncellemeler", text.lower())
        self.assertIn(get_version(), text)

    def test_turkish_codename_present(self):
        rel = release_for_version("4.7.0")
        if rel:
            self.assertTrue(rel.get("codename"))
            self.assertTrue(rel.get("story"))


class UpdatesHookTests(unittest.TestCase):
    def test_install_syncs_reexport(self):
        from diplomacy_bot.telegram_updates import install_updates_post_init
        from diplomacy_bot import telegram_app as ta
        from diplomacy_bot import callbacks as cb

        install_updates_post_init()
        self.assertIs(ta._handle_callback, cb.handle_callback)


if __name__ == "__main__":
    unittest.main()
