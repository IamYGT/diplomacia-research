#!/usr/bin/env python3
"""Tüm bot API yollarını sırayla dener — safe GET/POST ping varsayılan."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diplomacy_bot.account_runtime import account_context  # noqa: E402
from diplomacy_bot.api_route_probe import run_probe_suite  # noqa: E402
from diplomacy_bot.api_route_registry import find_unregistered_routes  # noqa: E402
from diplomacy_bot.api_route_replay import run_replay_suite  # noqa: E402
from diplomacy_bot.game_api import api  # noqa: E402
from diplomacy_bot.store import get_account, init_db  # noqa: E402


def _api_fn(method: str, path: str, token: str, body=None, delay: float = 0.12):
    return api(method, path, token, body, delay=delay)


def main() -> int:
    p = argparse.ArgumentParser(description="Bot API route probe — registry sözleşmesi")
    p.add_argument("account", nargs="?", default="ygt", help="DB hesap adı")
    p.add_argument("--mutate", action="store_true", help="State değiştiren POST'ları da dene (dikkat)")
    p.add_argument("--check-registry", action="store_true", help="Sadece kod vs registry uyumu")
    p.add_argument("--replay", action="store_true", help="Kayıtlı cassette ile tüm route'ları doğrula (ağ yok)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    missing = find_unregistered_routes()
    if missing:
        print("UYARI: registry dışı kod yolları:", file=sys.stderr)
        for m, path in missing:
            print(f"  {m} {path}", file=sys.stderr)

    if args.check_registry:
        return 1 if missing else 0

    if args.replay:
        report = run_replay_suite()
        report["registry_gaps"] = [{"method": m, "path": path} for m, path in missing]
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(
                f"replay ok={report['ok']} pass={report['passed']}/{report['total']}"
            )
        return 0 if report["ok"] and not missing else 1

    init_db()
    acc = get_account(args.account)
    if not acc:
        print(json.dumps({"ok": False, "error": f"hesap yok: {args.account}"}))
        return 1

    with account_context(acc):
        report = run_probe_suite(_api_fn, acc.token, safe_only=not args.mutate)

    report["account"] = args.account
    report["registry_gaps"] = [{"method": m, "path": path} for m, path in missing]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"account={args.account} ok={report['ok']} pass={report['passed']}/{report['total']} skip={report['skipped']}")
        for r in report["results"]:
            if r.get("skipped"):
                print(f"  SKIP {r['route_id']} ({r.get('reason')})")
            elif r.get("ok"):
                print(f"  OK   {r['route_id']} {r['status']} {r['elapsed_ms']}ms")
            else:
                print(f"  FAIL {r['route_id']} {r.get('status')} {r.get('contract_error') or r.get('error')}")
        if missing:
            print(f"\nregistry gaps: {len(missing)} (pytest test_api_route_registry çalıştır)")

    return 0 if report["ok"] and not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
