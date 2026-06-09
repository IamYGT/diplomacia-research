#!/usr/bin/env python3
"""Client bundle + api_catalog birleşimi → docs/public api-endpoints.json."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path("/tmp/diplomacia-index.js")
CATALOG = ROOT / "bot" / "data" / "api_catalog.json"
OUT_DOCS = ROOT / "docs" / "api-endpoints.json"
OUT_PUBLIC = ROOT / "public" / "data" / "api-endpoints.json"

PREFIXES = (
    "auth", "auto", "block", "cabinet", "chat", "citizenship", "conferences", "countries",
    "diplomacy", "economy", "election", "elections", "factories", "init", "market",
    "military", "military-ops", "mod", "moderation", "online", "parliament", "parties",
    "players", "press", "provinces", "quests", "skills", "training-wars", "transfer",
    "upload", "visas", "wars", "world", "xp", "passive-skills",
)


def _is_api_path(path: str) -> bool:
    seg = path.lstrip("/").split("/")[0]
    return seg in PREFIXES


def from_bundle(js: str) -> list[dict]:
    endpoints: dict[tuple[str, str], dict] = {}

    for path, method in re.findall(
        r"h\(['\"]([^'\"]+)['\"],\{method:'(GET|POST|PUT|PATCH|DELETE)'", js
    ):
        p = path.split("?")[0]
        if _is_api_path(p):
            endpoints[(method, p)] = {"method": method, "path": p, "source": "bundle_literal"}

    for path, method in re.findall(
        r"h\(`([^`]+)`,\{method:'(GET|POST|PUT|PATCH|DELETE)'", js
    ):
        p = path.split("?")[0]
        if _is_api_path(p):
            endpoints[(method, p)] = {"method": method, "path": p, "source": "bundle_template"}

    for path in re.findall(r'["\'](/[a-z][a-z0-9_\-/{}?=&%.]{1,80})["\']', js, re.I):
        p = path.split("?")[0]
        if not _is_api_path(p):
            continue
        method = "GET" if any(
            p.endswith(s) or f"/{s}" in p
            for s in ("my", "status", "all", "history", "packages", "unread", "conversations")
        ) else "POST"
        key = (method, p)
        if key not in endpoints:
            endpoints[key] = {"method": method, "path": p, "source": "bundle_path_heuristic"}

    return list(endpoints.values())


def from_catalog() -> list[dict]:
    if not CATALOG.exists():
        return []
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out = []
    for ep in data.get("endpoints", []):
        out.append(
            {
                "method": ep["method"],
                "path": ep["path"].split("?")[0],
                "source": "api_catalog",
                "inferred": bool(ep.get("inferred")),
            }
        )
    return out


def merge(*sources: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    priority = {"bundle_literal": 3, "bundle_template": 3, "api_catalog": 2, "bundle_path_heuristic": 1}
    for src in sources:
        for ep in src:
            key = (ep["method"], ep["path"])
            cur = merged.get(key)
            if not cur or priority.get(ep.get("source", ""), 0) >= priority.get(cur.get("source", ""), 0):
                merged[key] = ep
    return sorted(merged.values(), key=lambda x: (x["path"], x["method"]))


def build_payload(endpoints: list[dict]) -> dict:
    modules = sorted(
        {
            "authAPI", "countriesAPI", "playersAPI", "blockAPI", "cabinetAPI",
            "factoryAPI", "electionAPI", "marketAPI", "chatAPI", "conferenceAPI",
            "militaryAPI", "warAPI", "militaryOpsAPI", "trainingWarAPI",
            "parliamentAPI", "diplomacyAPI", "autoAPI", "uploadAPI", "partyAPI",
            "questAPI", "transferAPI", "pressAPI", "provinceAPI", "modAPI",
            "visaAPI", "citizenshipAPI", "worldAPI", "moderationAPI", "skillsAPI",
            "passiveSkillsAPI", "economyAPI", "xpAPI",
        }
    )
    by_method: dict[str, int] = {}
    for ep in endpoints:
        by_method[ep["method"]] = by_method.get(ep["method"], 0) + 1
    return {
        "meta": {
            "source": str(BUNDLE),
            "catalog": str(CATALOG.relative_to(ROOT)),
            "base_url": "https://diplomacia.com.tr/api",
            "socket_url": "https://diplomacia.com.tr",
            "total_endpoints": len(endpoints),
            "by_method": by_method,
            "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "generator": "scripts/extract_endpoints.py",
        },
        "modules": modules,
        "endpoints": endpoints,
    }


def main() -> int:
    if not BUNDLE.exists():
        print(f"Bundle missing: {BUNDLE}", file=sys.stderr)
        return 1
    js = BUNDLE.read_text(encoding="utf-8", errors="ignore")
    endpoints = merge(from_bundle(js), from_catalog())
    payload = build_payload(endpoints)

    OUT_DOCS.parent.mkdir(parents=True, exist_ok=True)
    OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    OUT_DOCS.write_text(text + "\n", encoding="utf-8")
    OUT_PUBLIC.write_text(text + "\n", encoding="utf-8")

    print(f"endpoints={len(endpoints)} -> {OUT_DOCS}")
    print(f"by_method={payload['meta']['by_method']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
