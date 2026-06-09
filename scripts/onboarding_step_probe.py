#!/usr/bin/env python3
"""Onboarding complete-step replay testi — olgun hesapta çift ödül engeli."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = Path("/root/diplomacia-auth.json")
OUT = ROOT / "output" / "exploits"
BASE = "https://diplomacia.com.tr/api"
DELAY = 2.5
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def load_token() -> str:
    if not AUTH.exists():
        print(f"AUTH missing: {AUTH}", file=sys.stderr)
        sys.exit(1)
    return json.loads(AUTH.read_text())["token"]


def api(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Origin": "https://diplomacia.com.tr",
        "Referer": "https://diplomacia.com.tr/",
    }
    data = json.dumps(body).encode() if body is not None else None
    time.sleep(DELAY)
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def main() -> int:
    token = load_token()
    OUT.mkdir(parents=True, exist_ok=True)

    _, prof = api("GET", "/players/profile", token)
    player = prof.get("player", {})
    balance_start = int(player.get("balance") or 0)

    results: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "account": player.get("username"),
        "onboarding_step": player.get("onboarding_step"),
        "balance_start": balance_start,
        "step_replay": [],
    }

    for step in range(6):
        st, data = api("POST", "/players/complete-step", token, {"step": step})
        results["step_replay"].append(
            {
                "step": step,
                "status": st,
                "success": data.get("success"),
                "onboarding_step": data.get("onboarding_step"),
                "reward": data.get("reward"),
                "error": data.get("error"),
            }
        )
        flag = "BLOCKED" if data.get("success") is False else "GRANT"
        print(f"step {step}: HTTP {st} success={data.get('success')} [{flag}]")

    _, prof2 = api("GET", "/players/profile", token)
    balance_end = int(prof2.get("player", {}).get("balance") or 0)
    results["balance_end"] = balance_end
    results["balance_delta"] = balance_end - balance_start
    results["replay_safe"] = results["balance_delta"] == 0 and all(
        s.get("success") is False for s in results["step_replay"]
    )

    out_path = OUT / "onboarding_replay_probe.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreplay_safe={results['replay_safe']} delta={results['balance_delta']:+d}")
    print(f"saved {out_path}")
    return 0 if results["replay_safe"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
