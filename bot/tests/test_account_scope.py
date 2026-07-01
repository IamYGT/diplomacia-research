#!/usr/bin/env python3
"""Çoklu hesap izolasyonu + Telegram harness testleri."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot import auth, store
from diplomacy_bot.account_scope import (
    bind_intent_uid,
    install_account_scope_hooks,
    patch_telegram_easy_resolve,
    reset_intent_uid,
)
from diplomacy_bot.dashboard_markup import dashboard_inline_markup
from diplomacy_bot.modules.orchestrator import TickResult
from diplomacy_bot.telegram_harness import HarnessSession, cross_user_resolve_matrix
from diplomacy_bot.tick_activity import format_activity_line, record_tick_result


class AccountScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "scope.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_dashboard_switcher_only_own_accounts(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "tok100a", "p100", "A", telegram_user_id=100)
            store.add_account("u100_b", "tok100b", "p101", "B", telegram_user_id=100)
            store.add_account("u200_x", "tok200", "p200", "X", telegram_user_id=200)

            sess100 = HarnessSession(100)
            sess200 = HarnessSession(200)

            cbs100 = sess100.account_switcher_callbacks("u100_a")
            cbs200 = sess200.account_switcher_callbacks("u200_x")

            self.assertEqual(len(cbs100), 2)
            self.assertTrue(all("u100_" in cb for cb in cbs100))
            self.assertFalse(any("u200" in cb for cb in cbs100))
            self.assertEqual(len(cbs200), 0)

    def test_cross_user_resolve_matrix(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)

            s100 = HarnessSession(100)
            s200 = HarnessSession(200)
            matrix = cross_user_resolve_matrix(
                [s100, s200],
                ["u100_a", "u200_b"],
            )
            self.assertTrue(matrix[(100, "u100_a")])
            self.assertFalse(matrix[(100, "u200_b")])
            self.assertTrue(matrix[(200, "u200_b")])
            self.assertFalse(matrix[(200, "u100_a")])

    def test_nav_account_sets_default_only_if_owned(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)

            sess = HarnessSession(100)
            self.assertIsNone(sess.simulate_nav_account("u200_b"))
            self.assertNotEqual(sess.user_data.get("default_account"), "u200_b")

            acc = sess.simulate_nav_account("u100_a")
            self.assertIsNotNone(acc)
            self.assertEqual(sess.default_name(), "u100_a")

    def test_dashboard_markup_no_leak_without_user_accs(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            a1 = store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)

            mk = dashboard_inline_markup(a1, {}, user_accs=None)
            flat = [b.callback_data for row in mk.inline_keyboard for b in row]
            self.assertFalse(any(cb and "u200" in cb for cb in flat))

    def test_telegram_easy_resolve_scoped(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)
            patch_telegram_easy_resolve()
            from diplomacy_bot import telegram_easy as te

            acc, accs = te._resolve_account("u200_b", 100)
            self.assertIsNone(acc)
            self.assertEqual(len(accs), 1)

            acc2, _ = te._resolve_account("u100_a", 100)
            self.assertIsNotNone(acc2)
            self.assertEqual(acc2.name, "u100_a")

    def test_intent_multi_account_scoped(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)

            install_account_scope_hooks()
            from diplomacy_bot import intent_router as ir

            token = bind_intent_uid(100)
            try:
                with patch("diplomacy_bot.game_api.get_profile") as gp:
                    gp.return_value = MagicMock(username="A", level=5, balance=1000)
                    result = ir.try_fast_path("tüm hesaplar durum", "u100_a")
            finally:
                reset_intent_uid(token)

            self.assertIsNotNone(result)
            self.assertIn("u100_a", result.reply)
            self.assertNotIn("u200_b", result.reply)

    def test_stale_import_rebind_uses_accounts_picker(self):
        """main.py önce telegram_helpers import eder — hook sonrası yeni UI."""
        import diplomacy_bot.telegram_helpers as th

        before = th.format_accounts_html("x", [])
        install_account_scope_hooks()
        after_empty = th.format_accounts_html("x", [])
        self.assertIn("Henüz hesap yok", after_empty)
        self.assertNotIn("Diplomacia hesabını bağlamak", after_empty)

        from diplomacy_bot.store import Account

        acc = Account(
            id=1,
            name="ygt",
            token="t",
            player_id="p",
            username="Y.G.T",
            autofarm=True,
            last_farm_at=0.0,
            last_balance=1250,
            proxy_id="tor-02",
            proxy_url="",
            status="active",
            telegram_user_id=515491882,
        )
        html = th.format_accounts_html("ygt", [acc])
        self.assertIn("Hesaplarım", html)
        self.assertTrue("👑" in html or "⭐" in html)
        self.assertNotIn("şu an aktif hesap · Seçmek için", html)

        from diplomacy_bot.accounts_screen import send_accounts_picker

        self.assertIs(th._send_accounts_picker, send_accounts_picker)

        record_tick_result(
            "testacc",
            TickResult(account_name="testacc", ok=True, actions=[{"routine_daily": {"claimed": True}}]),
        )
        line = format_activity_line("testacc")
        self.assertIn("günlük", line)


    def test_execute_steps_rejects_foreign_account(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)
            from diplomacy_bot.ai_agent import execute_steps

            results, pending, blocked = execute_steps(
                [{"method": "GET", "path": "/players/profile", "account": "u200_b"}],
                "u100_a",
                telegram_user_id=100,
            )
            self.assertEqual(len(results), 1)
            self.assertIn("erişim yok", results[0].get("error", ""))

    def test_setmain_rejects_foreign_account(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)
            from diplomacy_bot.account_main import set_main_account

            with self.assertRaises(ValueError):
                set_main_account("u200_b", telegram_user_id=100)

    def test_mission_step_resolve_scoped(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)
            from diplomacy_bot.auth import resolve_account

            self.assertIsNone(resolve_account("u200_b", 100))
            self.assertIsNotNone(resolve_account("u100_a", 100))

    def test_legacy_ygt_claim_blocked_for_user(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("ygt", "t0", "p0", "Legacy", telegram_user_id=0)
            from diplomacy_bot.account_store_guard import install_store_guard_hooks

            install_store_guard_hooks()
            with self.assertRaises(ValueError):
                store.add_account("ygt", "t1", "p1", "Hijack", telegram_user_id=200)

    def test_u_prefix_claim_allowed(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u200_farm", "t0", "p0", "X", telegram_user_id=0)
            from diplomacy_bot.account_store_guard import install_store_guard_hooks

            install_store_guard_hooks()
            acc = store.add_account("u200_farm", "t1", "p1", "Y", telegram_user_id=200)
            self.assertEqual(acc.telegram_user_id, 200)

    def test_suggest_name_always_prefixed(self):
        from diplomacy_bot.connect_intel import suggest_new_account_name

        name = suggest_new_account_name(12345, "MyPlayer")
        self.assertTrue(name.startswith("u12345"))

    def test_harness_rejects_foreign_nav(self):
        with patch.object(store, "DB_PATH", self.db):
            store.init_db()
            store.add_account("u100_a", "t1", "p1", "A", telegram_user_id=100)
            store.add_account("u200_b", "t2", "p2", "B", telegram_user_id=200)
            s100 = HarnessSession(100)
            self.assertIsNone(s100.simulate_nav_account("u200_b"))
            self.assertEqual(s100.simulate_nav_account("u100_a").name, "u100_a")


if __name__ == "__main__":
    unittest.main()
