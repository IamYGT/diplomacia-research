#!/usr/bin/env python3
"""Token inbox scanner resilience tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TokenInboxScannerTests(unittest.TestCase):
    def test_scan_skips_bad_file_without_losing_good_tokens(self):
        from diplomacy_bot import token_watch

        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            good = inbox / "u42_01.jwt"
            bad = inbox / "u42_02.jwt"
            good.write_text("eyJgood.token.sig", encoding="utf-8")
            bad.write_text("eyJbad.token.sig", encoding="utf-8")

            def read_token(path: Path) -> str | None:
                if path.name == bad.name:
                    raise OSError("permission denied")
                return "eyJgood.token.sig"

            with (
                patch("diplomacy_bot.token_watch.TOKEN_INBOX", inbox),
                patch("diplomacy_bot.token_watch._inbox_mtime", {}),
                patch("diplomacy_bot.token_watch._read_token_from_path", side_effect=read_token),
            ):
                found = token_watch.scan_token_inbox(force=True)

        self.assertEqual(found, {"u42_01": "eyJgood.token.sig"})

    def test_fresh_candidates_skip_processed_token_hashes(self):
        from diplomacy_bot.token_watch import list_fresh_inbox_import_candidates

        with (
            patch(
                "diplomacy_bot.token_watch.list_inbox_import_candidates",
                return_value=[("u42_01", "tok-old"), ("u42_02", "tok-new")],
            ),
            patch(
                "diplomacy_bot.inbox_processed_state.is_inbox_candidate_processed",
                side_effect=lambda uid, name, token: token == "tok-old",
            ),
        ):
            fresh = list_fresh_inbox_import_candidates(42)

        self.assertEqual(fresh, [("u42_02", "tok-new")])


if __name__ == "__main__":
    unittest.main()
