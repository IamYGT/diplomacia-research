#!/usr/bin/env python3
"""Intent fast-path smoke — DB hesabı gerekir (ercan2)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.intent_router import try_fast_path
from diplomacy_bot.store import bootstrap_legacy, get_account, init_db


def main() -> int:
    init_db()
    bootstrap_legacy()
    if not get_account("ercan2"):
        print("SKIP: ercan2 hesabı yok")
        return 0

    cases = [
        "ne durumdayız",
        "ülke listele",
        "görev",
        "görev topla",
        "hap kullan",
        "savaş durumu",
        "farm yap",
    ]
    from diplomacy_bot.ai_agent import run_agent

    failed = 0
    teach = run_agent("can ne işe yarıyor", "ercan2")
    if not teach.reply or "Can" not in teach.reply:
        print("FAIL teach: can ne işe yarıyor")
        failed += 1
    else:
        print(f"OK teach: {teach.reply[:50].replace(chr(10), ' ')}…")
        if teach.inline_buttons:
            labels = [lb for lb, _ in teach.inline_buttons[0]]
            print(f"OK teach buttons: {labels}")
            from diplomacy_bot.game_coach import coach_action_buttons
            from diplomacy_bot.game_api import get_profile

            acc = get_account("ercan2")
            if acc:
                p = get_profile(acc.token)
                if p.health < 100 and p.health_pills > 0:
                    ordered = coach_action_buttons(p, "can")
                    if ordered and ordered[0][0][1] != "action:hap":
                        print("FAIL coach order: hap should be first when low health")
                        failed += 1

    auth = Path("/root/diplomacia-auth.json")
    probe_out = ROOT / "output" / "reverse" / "transfer_race_probe.json"
    if auth.exists():
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "transfer_race_probe.py")],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            print(f"FAIL transfer_race_probe: {r.stderr[:200]}")
            failed += 1
        elif probe_out.exists():
            status = json.loads(probe_out.read_text(encoding="utf-8")).get("status")
            if status not in ("skipped", "ok"):
                print(f"FAIL transfer_race status: {status}")
                failed += 1
            else:
                print(f"OK transfer_race: {status}")
        else:
            print("FAIL transfer_race: output missing")
            failed += 1
    else:
        print("SKIP transfer_race: no auth")

    for msg in cases:
        r = try_fast_path(msg, "ercan2")
        if r is None:
            print(f"FAIL no fast path: {msg}")
            failed += 1
        elif not r.reply or len(r.reply) < 5:
            print(f"FAIL empty reply: {msg}")
            failed += 1
        else:
            print(f"OK {msg}: {r.reply[:60].replace(chr(10), ' ')}…")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
