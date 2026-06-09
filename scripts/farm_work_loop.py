#!/usr/bin/env python3
"""
Tek hesap bakiye farm döngüsü (tutorial bittikten sonra).
factory_service.run_work_cycle kullanır — bot ile aynı eyalet/join mantığı.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

from diplomacy_bot.factory_service import run_work_cycle  # noqa: E402
from diplomacy_bot.game_api import get_profile  # noqa: E402

AUTH = Path("/root/diplomacia-auth.json")


def load() -> str:
    a = json.loads(AUTH.read_text(encoding="utf-8"))
    return a["token"]


def main() -> None:
    token = load()
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b0 = get_profile(token).balance
    print(f"Başlangıç bakiye: {b0:,}")

    for i in range(cycles):
        print(f"\n--- Döngü {i + 1}/{cycles} ---")
        result = run_work_cycle(token)
        if result.get("error"):
            print("Hata:", result["error"])
            if result.get("cooldown_ms"):
                print("Can bekleniyor — pill cooldown veya health regen")
            break
        earned = result.get("earned") or {}
        money = earned.get("money", 0)
        print("work OK", f"+{money} altın" if money else "")

    b1 = get_profile(token).balance
    print(f"\nSon bakiye: {b1:,}  (delta: {b1 - b0:+,})")


if __name__ == "__main__":
    main()
