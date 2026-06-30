#!/usr/bin/env python3
"""Wiki snapshot al, önceki ile karşılaştır, yeni API yollarını keşfet.

Kullanım:
  python3 scripts/wiki_update.py snapshot          # wiki'yi kaydet
  python3 scripts/wiki_update.py diff              # son iki snapshot diff
  python3 scripts/wiki_update.py discover          # diff + bot registry gap raporu
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diplomacy_bot.wiki_diff import compare_with_bot_registry, diff_snapshots, enrich_snapshot_api_paths  # noqa: E402
from diplomacy_bot.wiki_snapshot import (  # noqa: E402
    fetch_snapshot,
    load_manifest,
    load_snapshot,
    save_snapshot,
)


def cmd_snapshot(_args: argparse.Namespace) -> int:
    print("Wiki çekiliyor (MediaWiki API)…", flush=True)
    payload = fetch_snapshot(dedupe=True)
    dest = save_snapshot(payload)
    print(
        f"Kaydedildi: {dest}\n"
        f"  sayfa={payload['stored_pages']} api_path={len(payload['api_paths'])}"
    )
    if payload["api_paths"]:
        print("  API ipuçları:", ", ".join(payload["api_paths"][:12]))
    return 0


def _resolve_pair(args: argparse.Namespace) -> tuple[dict, dict]:
    manifest = load_manifest()
    if not manifest.get("current"):
        raise SystemExit("Snapshot yok — önce: wiki_update.py snapshot")
    new_id = args.new or manifest["current"]
    old_id = args.old or manifest.get("previous")
    if not old_id:
        raise SystemExit("Karşılaştırma için iki snapshot gerekli — bir kez daha snapshot alın")
    return load_snapshot(old_id), load_snapshot(new_id)


def cmd_diff(args: argparse.Namespace) -> int:
    old, new = _resolve_pair(args)
    report = diff_snapshots(old, new)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["summary"]
        print(
            f"Diff {report['old_snapshot']} → {report['new_snapshot']}: "
            f"+{s['added']} sayfa, ~{s['changed']} değişiklik, "
            f"+{s['new_api_paths']} yeni API yolu"
        )
        for ch in report["changed_pages"][:10]:
            print(f"  ~ {ch['title']}")
            if ch.get("new_api_paths"):
                print(f"      yeni API: {ch['new_api_paths']}")
        for ap in report["new_api_paths"]:
            print(f"  + API {ap}")
        for item in report["added_pages"][:8]:
            print(f"  + sayfa {item['title']}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    if not manifest.get("current"):
        raise SystemExit("Snapshot yok")
    current = enrich_snapshot_api_paths(load_snapshot(manifest["current"]))
    all_api = current.get("api_paths") or []
    reg_report = compare_with_bot_registry(all_api)

    diff_report = None
    if manifest.get("previous"):
        old = enrich_snapshot_api_paths(load_snapshot(manifest["previous"]))
        diff_report = diff_snapshots(old, current)

    out = {
        "snapshot": manifest["current"],
        "registry_gaps": reg_report,
        "diff": diff_report,
        "suggested_registry_additions": [],
    }

    candidates = set(reg_report.get("missing_in_registry") or [])
    if diff_report:
        candidates.update(diff_report.get("new_api_paths") or [])
        for ch in diff_report.get("changed_pages") or []:
            candidates.update(ch.get("new_api_paths") or [])

    for path in sorted(candidates):
        method = "GET" if any(
            path.endswith(s) or f"/{s}" in path
            for s in ("my", "status", "all", "history", "packages", "unread", "conversations")
        ) else "POST"
        out["suggested_registry_additions"].append(
            {"method": method, "path": path, "source": "wiki_snapshot"}
        )

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"Snapshot: {manifest['current']}")
        gaps = reg_report.get("missing_in_registry") or []
        print(f"Wiki'de olup registry'de yok: {len(gaps)}")
        for p in gaps[:15]:
            print(f"  ? {p}")
        if diff_report:
            s = diff_report["summary"]
            print(f"Son diff: +{s['new_api_paths']} API, ~{s['changed']} sayfa değişti")
        print(f"Önerilen ekleme: {len(out['suggested_registry_additions'])}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Diplomacia Wiki snapshot & diff")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("snapshot", help="Wiki'yi MediaWiki API ile kaydet")
    sp.set_defaults(func=cmd_snapshot)

    dp = sub.add_parser("diff", help="İki snapshot karşılaştır")
    dp.add_argument("--old", help="Eski snapshot id")
    dp.add_argument("--new", help="Yeni snapshot id")
    dp.add_argument("--json", action="store_true")
    dp.set_defaults(func=cmd_diff)

    disc = sub.add_parser("discover", help="Registry gap + wiki diff özeti")
    disc.add_argument("--json", action="store_true")
    disc.set_defaults(func=cmd_discover)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
