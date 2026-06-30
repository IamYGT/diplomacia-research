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


def run_pytest() -> None:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(BOT / "tests"), "-q", "--tb=no"],
            cwd=str(BOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError:
        record(WARN, "pytest", "pytest modülü yok")
        return
    except subprocess.TimeoutExpired:
        record(FAIL, "pytest", "timeout 180s")
        return
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = tail[-1] if tail else f"exit={proc.returncode}"
    if proc.returncode == 0:
        record(PASS, "pytest", summary)
    else:
        record(FAIL, "pytest", summary[:160])


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


def run_api_route_registry() -> None:
    from diplomacy_bot.api_route_registry import BOT_API_ROUTES, find_unregistered_routes

    missing = find_unregistered_routes()
    if missing:
        record(FAIL, "api_route_registry", f"{len(missing)} kayıtsız yol: {missing[:3]}")
    else:
        record(PASS, "api_route_registry", f"{len(BOT_API_ROUTES)} route tanımlı")


def run_wiki_registry_check() -> None:
    from diplomacy_bot.wiki_diff import wiki_registry_aligned

    wiki = wiki_registry_aligned()
    if wiki.get("skipped"):
        record(WARN, "wiki_registry", wiki.get("reason", "atlandı"))
    elif wiki.get("ok"):
        record(PASS, "wiki_registry", f"snapshot={wiki.get('snapshot')} aligned")
    else:
        miss = wiki.get("missing_in_registry") or []
        record(FAIL, "wiki_registry", f"{len(miss)} gap: {miss[:2]}")


def run_api_replay_contracts() -> None:
    from diplomacy_bot.api_route_replay import compare_catalog_vs_registry, run_replay_suite

    replay = run_replay_suite()
    if replay.get("ok"):
        record(PASS, "api_replay_cassette", f"{replay['passed']}/{replay['total']} route")
    else:
        detail = replay.get("missing_replay") or replay.get("contract_failures") or replay.get("failures")
        record(FAIL, "api_replay_cassette", str(detail)[:120])

    catalog = compare_catalog_vs_registry()
    if catalog.get("skipped"):
        record(WARN, "api_catalog_diff", catalog.get("reason", "?"))
    elif catalog.get("ok"):
        mm = len(catalog.get("method_mismatch") or [])
        record(PASS, "api_catalog_diff", f"bot⊆catalog method_warn={mm}")
    else:
        miss = catalog.get("missing_in_catalog") or []
        record(FAIL, "api_catalog_diff", f"{len(miss)} eksik: {miss[:2]}")


def run_api_route_probe() -> None:
    from diplomacy_bot.account_runtime import account_context
    from diplomacy_bot.api_route_probe import run_probe_suite
    from diplomacy_bot.game_api import api
    from diplomacy_bot.store import get_account, init_db, list_accounts

    init_db()
    accs = list_accounts()
    if not accs:
        record(WARN, "api_route_probe", "hesap yok — atlandı")
        return
    acc = accs[0]

    def _api(method, path, token, body=None, delay=0.12):
        return api(method, path, token, body, delay=delay)

    try:
        with account_context(acc):
            report = run_probe_suite(_api, acc.token, safe_only=True, delay=0.1)
        if report.get("ok"):
            record(PASS, "api_route_probe", f"{report['passed']}/{report['total']} safe route")
        else:
            fails = report.get("failures") or []
            detail = fails[0].get("contract_error") or fails[0].get("error") if fails else "?"
            record(FAIL, "api_route_probe", f"{report['failed_count']} fail — {detail[:80]}")
    except Exception as e:
        record(FAIL, "api_route_probe", str(e)[:120])


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
    run_pytest()
    run_api_route_registry()
    run_wiki_registry_check()
    run_api_replay_contracts()
    run_tor()
    run_accounts_api()
    run_api_route_probe()
    run_telegram()

    fails = sum(1 for s, _, _ in results if s == FAIL)
    print(f"\n=== Özet: {len(results)} kontrol, {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
