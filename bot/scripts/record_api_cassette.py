#!/usr/bin/env python3
"""Canlı API probe → tests/fixtures/api_replay.json cassette güncelle."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diplomacy_bot.account_runtime import account_context  # noqa: E402
from diplomacy_bot.api_route_replay import record_cassette_from_live  # noqa: E402
from diplomacy_bot.game_api import api  # noqa: E402
from diplomacy_bot.store import get_account, init_db  # noqa: E402


def _api_fn(method: str, path: str, token: str, body=None, delay: float = 0.12):
    return api(method, path, token, body, delay=delay)


def main() -> int:
    p = argparse.ArgumentParser(description="Canlı yanıtları api_replay.json'a kaydet")
    p.add_argument("account", nargs="?", default="ygt", help="DB hesap adı")
    p.add_argument(
        "--mutate",
        action="store_true",
        help="State değiştiren POST'ları da kaydet (dikkat — fabrika/savaş/hap)",
    )
    p.add_argument("--dry-run", action="store_true", help="Dosyaya yazma, sadece rapor")
    p.add_argument("--delay", type=float, default=0.12, help="İstekler arası bekleme (sn)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    init_db()
    acc = get_account(args.account)
    if not acc:
        print(json.dumps({"ok": False, "error": f"hesap yok: {args.account}"}))
        return 1

    with account_context(acc):
        report = record_cassette_from_live(
            _api_fn,
            acc.token,
            include_mutating=args.mutate,
            delay=args.delay,
            dry_run=args.dry_run,
        )
    report["account"] = args.account

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        mode = "DRY" if args.dry_run else "WROTE"
        print(
            f"[{mode}] account={args.account} recorded={len(report['recorded'])} "
            f"skipped={len(report['skipped'])} replay={report.get('replay_passed')}/{report.get('replay_total')}"
        )
        if report.get("contract_failures"):
            for f in report["contract_failures"][:5]:
                print(f"  CONTRACT {f}")
        if not report.get("ok"):
            print("  UYARI: sözleşme hatası var — cassette yine de birleştirildi" if not args.dry_run else "  DRY-RUN")

    return 0 if report.get("replay_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
