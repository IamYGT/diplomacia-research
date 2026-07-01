#!/usr/bin/env python3
"""Mimari patron CI kontrolü — satır limiti + yasak import."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "diplomacy_bot"
MAX_LINES = 300
SKIP = {
    "store.py",
    "telegram_app.py",
    "telegram_ui.py",
    "callbacks.py",
    "game_features.py",
    "intent_router.py",
    "stat_board.py",
    "feature_reports.py",
    "factory_board.py",
    "easy_mode.py",
    "farm_board.py",
    "feature_handlers.py",
    "game_coach.py",
    "ai_agent.py",
    "api_route_replay.py",
    "response_format.py",
    "modules/factory.py",
    "modules/stats.py",
    "diplomacy_bot/modules/factory.py",
    "diplomacy_bot/modules/stats.py",
    "stat_queue.py",
    "telegram_helpers.py",
    "token_recovery_hooks.py",
    "war_board.py",
}
FORBIDDEN = [
    (re.compile(r"^from \.telegram_ui import format_accounts_html"), "telegram_ui format_accounts_html üst import"),
    (re.compile(r"list_accounts\(\)"), "list_accounts() — scoped_list_accounts kullan"),
]


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def main() -> int:
    errors: list[str] = []
    for path in sorted(PKG.rglob("*.py")):
        if path.name.startswith("__"):
            continue
        n = count_lines(path)
        rel = path.relative_to(ROOT)
        if n > MAX_LINES and path.name not in SKIP and str(rel) not in SKIP:
            errors.append(f"{rel}: {n} satır (limit {MAX_LINES})")
        if path.name in ("auth.py", "fleet_status.py", "accounts_picker.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for pat, msg in FORBIDDEN:
                if pat.search(text) and "scoped_list_accounts" not in msg:
                    if "list_accounts()" in msg and "scoped_list_accounts" in text:
                        continue
                    if pat.search(text):
                        errors.append(f"{rel}: {msg}")

    if errors:
        print("ARCH CHECK FAIL")
        for e in errors[:40]:
            print(" -", e)
        if len(errors) > 40:
            print(f" ... +{len(errors) - 40} more")
        return 1
    print(f"ARCH CHECK OK ({len(list(PKG.rglob('*.py')))} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
