#!/usr/bin/env python3
"""Discover Diplomacia frontend API paths from static web bundles."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diplomacy_bot.api_route_registry import normalize_route_path, registry_keys  # noqa: E402

HOME = "https://diplomacia.com.tr/"
_SCRIPT_RE = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.I)
_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])['`](/[-A-Za-z0-9_./:${}]+(?:\?[^'`]*)?)['`]")
_METHOD_RE = re.compile(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]")
_PATH_KEYWORDS = (
    "/auth",
    "/auto",
    "/cabinet",
    "/chat",
    "/citizenship",
    "/countries",
    "/elections",
    "/factories",
    "/market",
    "/military",
    "/online",
    "/parliament",
    "/players",
    "/press",
    "/provinces",
    "/quests",
    "/training-wars",
    "/visas",
    "/wars",
)
CAPABILITY_KEYWORDS = {
    "work": ("work", "employment", "permit"),
    "training": ("training-wars",),
}


def _fetch(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "DiplomacyBotApiDiscovery/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _bundle_urls(home_html: str, base_url: str) -> list[str]:
    urls: list[str] = []
    for src in _SCRIPT_RE.findall(home_html):
        url = urllib.parse.urljoin(base_url, src)
        if url.endswith(".js") and url not in urls:
            urls.append(url)
    return urls


def _guess_method(text: str, start: int) -> str:
    next_call = text.find("h(", start)
    end = next_call if next_call != -1 else min(len(text), start + 220)
    window = text[start:end]
    match = _METHOD_RE.search(window)
    return match.group(1) if match else "GET"


def _is_api_path(path: str) -> bool:
    return path.startswith(_PATH_KEYWORDS) and not path.startswith("/assets/")


def discover_paths(base_url: str = HOME) -> dict:
    home = _fetch(base_url)
    bundles = _bundle_urls(home, base_url)
    found: dict[tuple[str, str], set[str]] = {}
    for bundle_url in bundles:
        text = _fetch(bundle_url)
        for match in _PATH_RE.finditer(text):
            raw = match.group(1)
            if not _is_api_path(raw):
                continue
            method = _guess_method(text, match.end())
            path = normalize_route_path(raw)
            found.setdefault((method, path), set()).add(bundle_url)
    reg = registry_keys()
    paths = [
        {"method": m, "path": p, "registered": (m, p) in reg, "sources": sorted(s)}
        for (m, p), s in sorted(found.items())
    ]
    return {"home": base_url, "bundles": bundles, "routes": paths}


def summarize_capability_candidates(report: dict) -> list[dict]:
    routes = list(report.get("routes") or [])
    summary: list[dict] = []
    for label, needles in CAPABILITY_KEYWORDS.items():
        hits = [
            r
            for r in routes
            if any(needle in str(r.get("path", "")).lower() for needle in needles)
        ]
        summary.append(
            {
                "label": label,
                "count": len(hits),
                "routes": hits,
            }
        )
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=HOME)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "frontend_api_discovery.json")
    ap.add_argument("--show-missing", action="store_true")
    args = ap.parse_args()

    report = discover_paths(args.base_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = [r for r in report["routes"] if not r["registered"]]
    print(f"bundles={len(report['bundles'])} routes={len(report['routes'])} missing={len(missing)}")
    for item in summarize_capability_candidates(report):
        sample = ", ".join(f"{r['method']} {r['path']}" for r in item["routes"][:4])
        suffix = f" — {sample}" if sample else ""
        print(f"capability:{item['label']} candidates={item['count']}{suffix}")
    if args.show_missing:
        for r in missing:
            print(f"{r['method']:6} {r['path']}")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
