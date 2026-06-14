#!/usr/bin/env python3
"""Tek seferlik Telegram test mesajı — token argüman veya .env."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

BOT = Path(__file__).resolve().parents[1] / "bot"
load_dotenv(BOT / ".env")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--token", help="BotFather token")
    p.add_argument("--admin", help="Telegram user id (chat_id)")
    p.add_argument("--text", default="🤖 Diplomacia bot Hetzner smoke test — bağlantı OK")
    args = p.parse_args()

    token = (args.token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    admin = (args.admin or os.environ.get("TELEGRAM_ADMIN_IDS", "")).split(",")[0].strip()

    if not token or token == "your_bot_token_here":
        print("HATA: TELEGRAM_BOT_TOKEN gerekli")
        print("  python3 scripts/send_test_message.py --token 'XXX:YYY' --admin '123456789'")
        return 1
    if not admin.isdigit():
        print("HATA: TELEGRAM_ADMIN_IDS (sayısal user id) gerekli")
        return 1

    me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15).json()
    if not me.get("ok"):
        print("getMe FAIL:", me)
        return 1
    print("Bot:", me["result"].get("username"))

    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": int(admin), "text": args.text},
        timeout=15,
    ).json()
    if r.get("ok"):
        print("Mesaj gönderildi → chat_id", admin)
        return 0
    print("sendMessage FAIL:", r)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
