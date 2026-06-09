#!/usr/bin/env python3
"""Aktif bakiye avı — quest claim, use-pills, work döngüsü, market satış."""
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

AUTH = Path("/root/diplomacia-auth.json")
BASE = "https://diplomacia.com.tr/api"
OUT = Path(__file__).resolve().parents[1] / "output" / "exploits"
DELAY = 2.8


def load():
    a = json.loads(AUTH.read_text())
    return a["token"], a["player_id"]


def api(method, path, token, body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://diplomacia.com.tr",
    }
    data = json.dumps(body).encode() if body is not None else None
    time.sleep(DELAY)
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": "parse fail"}


def profile(token):
    st, d = api("GET", "/players/profile", token)
    p = d.get("player", {})
    return p.get("balance", 0), p.get("diamonds", 0), p.get("health", 0), p.get("health_pills", 0)


def step(log, name, token, method, path, body=None):
    b0 = profile(token)
    st, data = api(method, path, token, body)
    b1 = profile(token)
    delta = b1[0] - b0[0]
    entry = {"name": name, "status": st, "balance_delta": delta, "before": b0[0], "after": b1[0],
             "health": b1[2], "response": str(data)[:350]}
    log.append(entry)
    mark = "💰" if delta > 0 else "·"
    print(f"{mark} {name}: {b0[0]} -> {b1[0]} ({delta:+d}) HTTP {st}")
    return data, delta


def main():
    token, pid = load()
    log = []
    print("=== BAKIYE AVI ===\n")

    # 1. Quest claim (work_1 tamamlanmış)
    st, quests = api("GET", "/quests", token)
    for q in quests.get("quests", []):
        if q.get("progress", 0) >= q.get("target", 1) and not q.get("rewarded"):
            step(log, f"quest_claim_{q.get('quest_key')}", token, "POST", f"/quests/{q['id']}/claim", {})

    # 2. Can iksiri kullan
    step(log, "auto_use_pills", token, "POST", "/auto/use-pills", {})

    # 3. Fabrikada çalış (3x — quest work_3 için)
    for i in range(3):
        _, d = step(log, f"factory_work_{i+1}", token, "POST", "/factories/work", {})
        if d and "error" in str(d).lower() and "can" in str(d).lower():
            step(log, "auto_use_pills_retry", token, "POST", "/auto/use-pills", {})
            step(log, f"factory_work_retry_{i+1}", token, "POST", "/factories/work", {})

    # 4. Yeni quest claim
    st, quests = api("GET", "/quests", token)
    for q in quests.get("quests", []):
        if q.get("progress", 0) >= q.get("target", 1) and not q.get("rewarded"):
            step(log, f"quest_claim2_{q.get('quest_key')}", token, "POST", f"/quests/{q['id']}/claim", {})

    # 5. Market — deri sat (ucuz, hızlı dolum)
    step(log, "market_sell_deri", token, "POST", "/market/list", {"resource": "deri", "quantity": 10, "unit_price": 50})

    # 6. Günlük ödül tekrar
    step(log, "daily_claim", token, "POST", "/players/daily-claim", {})

    total = sum(x["balance_delta"] for x in log)
    report = {"run_at": datetime.utcnow().isoformat() + "Z", "total_delta": total, "steps": log}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "balance_hunt_now.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTOPLAM DELTA: {total:+d}")
    gains = [x for x in log if x["balance_delta"] > 0]
    print(f"Kazandıran adım: {len(gains)}")
    for g in gains:
        print(f"  +{g['balance_delta']} — {g['name']}")


if __name__ == "__main__":
    main()
