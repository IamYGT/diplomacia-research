"""Token recovery testleri."""

from __future__ import annotations

import unittest

from diplomacy_bot.token_recovery import (
    extract_jwt_from_text,
    format_token_recovery_html,
    is_token_auth_error,
)


class TokenRecoveryTests(unittest.TestCase):
    def test_detects_403(self):
        self.assertTrue(is_token_auth_error("profile HTTP 403", http_status=403))

    def test_detects_gecersiz(self):
        self.assertTrue(is_token_auth_error("Token geçersiz"))

    def test_ignores_timeout(self):
        self.assertFalse(is_token_auth_error("API zaman aşımı"))

    def test_extract_jwt(self):
        raw = "prefix eyJhbGciOiJIUzI1NiJ9.abc.def suffix"
        self.assertTrue(extract_jwt_from_text(raw).startswith("eyJ"))

    def test_recovery_html_has_steps(self):
        html = format_token_recovery_html("ygt")
        self.assertIn("Console", html)
        self.assertIn("eyJ", html)
        self.assertIn("ygt", html)


if __name__ == "__main__":
    unittest.main()
