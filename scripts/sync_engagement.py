#!/usr/bin/env python3
"""Pentest engagement loglarını diplomacia-research ile birleştirir."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENG = Path(os.environ.get("DIPLOMACIA_ENGAGEMENT_DIR", Path.home() / "pentest-logs/engagements/diplomacia"))
RAW = Path(os.environ.get("DIPLOMACIA_RAW_DIR", Path.home() / "pentest-logs/raw/diplomacia"))
OUT = REPO / "engagement" / "intel"
LINKS = REPO / "engagement"


def _read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e), "_path": str(path)}


def _symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return
        link.unlink()
    elif link.exists():
        return
    if target.exists():
        link.symlink_to(target)


def merge_intel() -> dict:
    findings = _read_json(ENG / "findings.json") or {}
    knowledge = _read_json(ENG / "knowledge_pool.json") or {}
    manifest = _read_json(ENG / "manifest.json") or {}
    api_map = _read_json(ENG / "api_map.json") or _read_json(RAW / "github_research/docs__api-endpoints.json")

    learnings = knowledge.get("learnings", []) if isinstance(knowledge, dict) else []
    stealth = knowledge.get("stealth", {}) if isinstance(knowledge, dict) else {}

    merged = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "target": findings.get("target") or manifest.get("target") or "https://diplomacia.com.tr",
        "engagement_dir": str(ENG),
        "raw_dir": str(RAW),
        "findings_count": len(findings.get("findings", [])),
        "findings": findings.get("findings", []),
        "learnings_count": len(learnings),
        "learnings": learnings[-30:],  # son 30
        "stealth": stealth,
        "stack": manifest.get("stack", {}),
        "multi_account": {
            "cluster_threshold": 3,
            "signals": ["push_token", "ip_24h", "ip_7d", "reg_ip", "transfer", "similar_name"],
            "auto_ban": False,
            "doc": "docs/45-multi-account-ban-research.md",
        },
        "telegram_osint": manifest.get("osint", {}).get("telegram", {}),
        "api_endpoints_count": len(api_map.get("endpoints", [])) if isinstance(api_map, dict) else 0,
    }
    return merged


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    merged = merge_intel()
    out_path = OUT / "merged.json"
    out_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path} ({merged['findings_count']} findings, {merged['learnings_count']} learnings)")

    _symlink(ENG, LINKS / "pentest")
    _symlink(RAW, LINKS / "raw")
    _symlink(ENG / "docs", LINKS / "docs")
    print(f"Symlinks: {LINKS}/pentest, raw, docs")


if __name__ == "__main__":
    main()
