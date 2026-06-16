#!/usr/bin/env python3
"""PM2/shell wrapper sonrası Telegram crash bildirimi."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.crash_notify import send_crash_notify


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--exit", type=int, default=1, help="Process exit code")
    p.add_argument("--log", default="", help="Son log satırları")
    p.add_argument("--title", default="Bot process çöktü (PM2)")
    p.add_argument("--detail", default="")
    args = p.parse_args()

    detail = args.detail or f"exit_code={args.exit}"
    if args.log:
        detail += f"\n\n--- son log ---\n{args.log.strip()[-2000:]}"

    ok = send_crash_notify(
        args.title,
        detail,
        dedupe_key=f"pm2-exit:{args.exit}:{detail[:60]}",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
