#!/usr/bin/env python3
"""Tam doğrulama: unittest + Tor + DB + API + Telegram getMe/sendMessage."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOT = REPO / "bot"
sys.path.insert(0, str(BOT))

from dotenv import load_dotenv

load_dotenv(BOT / ".env")

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "·")
    print(f"{icon} {name}" + (f" — {detail}" if detail else ""))


def run_unittests() -> None:
    loader = unittest.TestLoader()
    suite = loader.discover(str(BOT / "tests"))
    r = unittest.TextTestRunner(verbosity=0).run(suite)
    if r.wasSuccessful():
        record(PASS, "unittest", f"{r.testsRun} test")
    else:
        record(FAIL, "unittest", f"failures={len(r.failures)} errors={len(r.errors)}")


def run_tor() -> None:
    from diplomacy_bot.tor_pool import rotate_newnym, tor_socks_url

    if not Path("/var/run/tor/control.authcookie").exists():
        record(WARN, "tor", "cookie yok")
        return
    ok = rotate_newnym()
    if not ok:
        record(FAIL, "tor_newnym", "NEWNYM başarısız")
        return
    record(PASS, "tor_newnym")
    try:
        ip = subprocess.check_output(
            ["curl", "-s", "--max-time", "12", "--proxy", tor_socks_url(), "https://api.ipify.org"],
            text=True,
        ).strip()
        record(PASS, "tor_egress", f"exit={ip}")
    except Exception as e:
        record(FAIL, "tor_egress", str(e))


def run_accounts_api() -> None:
    from diplomacy_bot.account_runtime import run_for_account
    from diplomacy_bot.game_api import get_profile
    from diplomacy_bot.store import init_db, list_accounts

    init_db()
    accs = list_accounts()
    if not accs:
        record(WARN, "accounts_db", "hesap yok")
        return
    for a in accs:
        try:
            p = run_for_account(a, get_profile, a.token)
            record(PASS, f"api_profile:{a.name}", f"{p.username} lv{p.level} proxy={a.proxy_id}")
        except Exception as e:
            record(FAIL, f"api_profile:{a.name}", str(e)[:120])


def run_telegram() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "your_bot_token_here":
        record(FAIL, "telegram", "TELEGRAM_BOT_TOKEN eksik — bot/.env doldur")
        return

    import requests

    me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15).json()
    if not me.get("ok"):
        record(FAIL, "telegram_getMe", str(me)[:200])
        return
    bot_user = me["result"].get("username", "?")
    record(PASS, "telegram_getMe", f"@{bot_user}")

    raw_admins = os.environ.get("TELEGRAM_ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()]
    if not admin_ids:
        record(WARN, "telegram_send", "TELEGRAM_ADMIN_IDS yok — mesaj atlanıyor")
        return

    text = (
        "🤖 Diplomacia bot doğrulama\n"
        "✅ verify_bot.py smoke test\n"
        "Tor + API + DB hazır."
    )
    for chat_id in admin_ids:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        ).json()
        if r.get("ok"):
            record(PASS, "telegram_sendMessage", f"chat_id={chat_id}")
        else:
            record(FAIL, "telegram_sendMessage", str(r)[:200])


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--token", help="Telegram bot token (override .env)")
    p.add_argument("--admin", help="Telegram admin user id (override .env)")
    args = p.parse_args()
    if args.token:
        os.environ["TELEGRAM_BOT_TOKEN"] = args.token
    if args.admin:
        os.environ["TELEGRAM_ADMIN_IDS"] = args.admin

    print("=== Diplomacia Bot Verify ===\n")
    subprocess.run([sys.executable, str(REPO / "scripts" / "sync_engagement.py")], check=False)
    run_unittests()
    run_tor()
    run_accounts_api()
    run_telegram()

    fails = sum(1 for s, _, _ in results if s == FAIL)
    print(f"\n=== Özet: {len(results)} kontrol, {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
