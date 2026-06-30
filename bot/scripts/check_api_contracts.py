#!/usr/bin/env python3
"""API sözleşme kontrolü — registry + replay + catalog diff + pytest."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diplomacy_bot.api_route_registry import BOT_API_ROUTES, find_unregistered_routes  # noqa: E402
from diplomacy_bot.api_route_replay import compare_catalog_vs_registry, run_replay_suite  # noqa: E402
from diplomacy_bot.wiki_diff import wiki_registry_aligned  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="API contract check — CI rutini")
    p.add_argument("--pytest", action="store_true", help="pytest test_api_route_*.py de koş")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    missing = find_unregistered_routes()
    catalog = compare_catalog_vs_registry()
    replay = run_replay_suite()
    wiki = wiki_registry_aligned()

    report = {
        "ok": not missing and catalog.get("ok", True) and replay.get("ok") and wiki.get("ok", True),
        "registry_gaps": [{"method": m, "path": path} for m, path in missing],
        "catalog": catalog,
        "replay": {
            "ok": replay.get("ok"),
            "passed": replay.get("passed"),
            "total": replay.get("total"),
            "missing_replay": replay.get("missing_replay"),
        },
        "route_count": len(BOT_API_ROUTES),
        "wiki": wiki,
    }

    if args.pytest:
        pytest_bin = ROOT / ".venv" / "bin" / "pytest"
        pytest_cmd = [str(pytest_bin)] if pytest_bin.exists() else [sys.executable, "-m", "pytest"]
        proc = subprocess.run(
            [
                *pytest_cmd,
                "tests/test_api_route_registry.py",
                "tests/test_api_route_replay.py",
                "tests/test_record_api_cassette.py",
                "tests/test_wiki_snapshot.py",
                "tests/test_wiki_mechanic_hints.py",
                "-q",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        report["pytest"] = {"ok": proc.returncode == 0, "output": proc.stdout[-2000:]}
        if proc.returncode != 0:
            report["ok"] = False
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        icon = "OK" if report["ok"] else "FAIL"
        print(f"[{icon}] routes={report['route_count']} registry_gaps={len(missing)}")
        print(
            f"  replay {replay.get('passed')}/{replay.get('total')} "
            f"catalog_ok={catalog.get('ok')} wiki_ok={wiki.get('ok')}"
        )
        if missing:
            for m, path in missing:
                print(f"  GAP {m} {path}")
        if not wiki.get("ok") and not wiki.get("skipped"):
            for p in (wiki.get("missing_in_registry") or [])[:5]:
                print(f"  WIKI_GAP {p}")
        if not catalog.get("ok"):
            for item in catalog.get("missing_in_catalog", [])[:5]:
                print(f"  CATALOG {item['method']} {item['path']}")
        if args.pytest and report.get("pytest"):
            print(f"  pytest {'PASS' if report['pytest']['ok'] else 'FAIL'}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
