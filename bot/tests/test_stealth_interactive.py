#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.stealth_client import (
    reset_interactive_fast,
    set_interactive_fast,
    stealth_request,
)


class StealthInteractiveTests(unittest.TestCase):
    def test_interactive_uses_shorter_delay(self):
        sleeps: list[float] = []

        def _fake_sleep(sec: float) -> None:
            sleeps.append(sec)

        tok = set_interactive_fast(True)
        try:
            with patch("diplomacy_bot.stealth_client.time.sleep", _fake_sleep):
                with patch("diplomacy_bot.stealth_client._http_via_requests", return_value=(200, "{}")):
                    with patch("diplomacy_bot.stealth_client.get_request_proxy", return_value="socks5h://127.0.0.1:9050"):
                        stealth_request("GET", "https://example.com", delay=0.3)
        finally:
            reset_interactive_fast(tok)

        self.assertTrue(sleeps)
        self.assertLess(sleeps[0], 1.0)

    def test_background_uses_longer_delay(self):
        sleeps: list[float] = []

        def _fake_sleep(sec: float) -> None:
            sleeps.append(sec)

        with patch("diplomacy_bot.stealth_client.time.sleep", _fake_sleep):
            with patch("diplomacy_bot.stealth_client._http_via_requests", return_value=(200, "{}")):
                with patch("diplomacy_bot.stealth_client.get_request_proxy", return_value="socks5h://127.0.0.1:9050"):
                    with patch("diplomacy_bot.stealth_client.load_rules") as lr:
                        lr.return_value.min_request_delay_sec = 6
                        lr.return_value.cooldown_on_429_sec = 180
                        stealth_request("GET", "https://example.com")
        self.assertGreater(sleeps[0], 5.0)

    def test_429_returns_immediately_without_retry(self):
        """429'da sleep(retryAfter) × 3 retry YAPMADAN hemen döner — arka plan job blokajı yok.

        Eski kod her 429'da sleep(ra+5) yapıp 3 kez retry ediyordu (~290sn blokaj).
        Yeni davranış: cooldown set edilip tek çağrıda dönüş.
        """
        sleeps: list[float] = []

        def _fake_sleep(sec: float) -> None:
            sleeps.append(sec)

        calls = {"n": 0}

        def _fake_http(method, url, hdrs, data, proxy, timeout):
            calls["n"] += 1
            return (429, '{"error":"rate_limited","retryAfter":90}')

        import diplomacy_bot.stealth_client as sc
        sc._last_429_at = 0.0  # cooldown temiz — pre-call sleep'i bypass

        with patch("diplomacy_bot.stealth_client.time.sleep", _fake_sleep):
            with patch("diplomacy_bot.stealth_client._http_via_requests", side_effect=_fake_http):
                with patch("diplomacy_bot.stealth_client.get_request_proxy", return_value="socks5h://127.0.0.1:9050"):
                    with patch("diplomacy_bot.stealth_client.load_rules") as lr:
                        lr.return_value.min_request_delay_sec = 0
                        lr.return_value.cooldown_on_429_sec = 180
                        st, body = stealth_request("POST", "https://example.com/upgrade")

        self.assertEqual(st, 429)
        self.assertEqual(calls["n"], 1)  # retry yok — tek çağrı
        # 429 sleep'i (ra+5 ≈ 95sn) olmamalı; sadece stealth delay (≤1.5sn) kabul
        self.assertFalse(
            any(s > 5 for s in sleeps),
            f"429 retry sleep tespit edildi (job blokajı): {sleeps}",
        )


if __name__ == "__main__":
    unittest.main()
