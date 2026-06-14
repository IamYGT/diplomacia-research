#!/usr/bin/env python3
"""Semantik versiyon bump — bot/VERSION + CHANGELOG başlığı."""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "bot"
VERSION_FILE = ROOT / "VERSION"
CHANGELOG = ROOT / "CHANGELOG.md"


def parse_version(v: str) -> tuple[int, int, int]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", v.strip())
    if not m:
        raise SystemExit(f"Geçersiz VERSION: {v}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump(v: str, part: str) -> str:
    major, minor, patch = parse_version(v)
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("part", choices=["major", "minor", "patch"], default="patch", nargs="?")
    p.add_argument("--note", default="Güncelleme")
    args = p.parse_args()

    old = VERSION_FILE.read_text(encoding="utf-8").strip()
    new = bump(old, args.part)
    VERSION_FILE.write_text(new + "\n", encoding="utf-8")

    today = date.today().isoformat()
    header = f"\n## [{new}] — {today}\n\n### {args.note}\n"
    if CHANGELOG.exists():
        text = CHANGELOG.read_text(encoding="utf-8")
        insert_at = text.find("\n## [")
        if insert_at == -1:
            text += header
        else:
            text = text[:insert_at] + header + text[insert_at:]
        CHANGELOG.write_text(text, encoding="utf-8")

    print(f"{old} → {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
