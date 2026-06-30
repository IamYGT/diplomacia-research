#!/usr/bin/env python3
"""Canlı bot/API sağlık kontrolü — snapshot + dashboard yayın simülasyonu."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diplomacy_bot.dynamic_context import peek_snapshot_cache, snapshot_account  # noqa: E402
from diplomacy_bot.store import get_account, init_db  # noqa: E402
from diplomacy_bot.telegram_ui import format_dashboard_html  # noqa: E402


def probe_once(account: str, *, refresh: bool) -> dict:
    init_db()
    acc = get_account(account)
    if not acc:
        return {"ok": False, "error": f"hesap yok: {account}"}
    t0 = time.time()
    snap = snapshot_account(acc, force_refresh=refresh)
    elapsed = round(time.time() - t0, 2)
    err = snap.get("error")
    live = not err
    html_len = len(format_dashboard_html(acc, snap)) if snap else 0
    return {
        "ok": live,
        "account": account,
        "username": snap.get("username") or acc.username,
        "balance": snap.get("balance"),
        "level": snap.get("level"),
        "error": err,
        "elapsed_sec": elapsed,
        "dashboard_html_len": html_len,
        "cache_stale": bool(peek_snapshot_cache(account, allow_stale=True)),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Bot canlı veri probu")
    p.add_argument("account", nargs="?", default="ygt")
    p.add_argument("--loop", type=int, default=0, help="Her N saniyede tekrar (0=tek)")
    p.add_argument("--refresh", action="store_true", help="Önbelleği atla")
    args = p.parse_args()
    interval = max(0, args.loop)

    while True:
        result = probe_once(args.account, refresh=args.refresh)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if not interval:
            return 0 if result.get("ok") else 1
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
