#!/usr/bin/env bash
# Full crawl + security audit verify (goal completion surface).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "== verify-audit =="

test -f "$ROOT/docs/00-index.md" || fail "missing docs/00-index.md"
test -f "$ROOT/docs/11-audit-summary.md" || fail "missing docs/11-audit-summary.md"
test -f "$ROOT/docs/api-endpoints.json" || fail "missing docs/api-endpoints.json"
test -f "$ROOT/output/security/findings.json" || fail "missing output/security/findings.json"
test -f "$ROOT/output/crawl/crawl_summary.json" || fail "missing crawl_summary.json"
test -f "$ROOT/output/audit_summary.json" || fail "missing audit_summary.json (run generate_audit_summary.py)"

python3 "$ROOT/scripts/generate_audit_summary.py" >/dev/null

python3 - "$ROOT/output/audit_summary.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d["security"]["critical_count"] == 0, "critical_count != 0"
assert d["exploits"]["onboarding_replay_safe"] is True
assert d["exploits"]["factory_idor_exploited"] == 0
assert d["socket_io"]["foreign_dm_received"] is False
assert d["endpoints"]["total"] >= 210
assert d["crawl"]["http_200"] >= 48
print("audit_summary OK: endpoints=", d["endpoints"]["total"], "critical=0")
PY

grep -q "11-audit-summary" "$ROOT/docs/00-index.md" || fail "00-index missing audit summary link"

# Key probe scripts exist
for s in full_audit.py extract_endpoints.py socket_transfer_probe.py generate_audit_summary.py onboarding_step_probe.py transfer_race_probe.py; do
  test -f "$ROOT/scripts/$s" || fail "missing scripts/$s"
done

# Transfer race probe (lv<5 skip veya lv5+ ok — auth varsa çalıştır)
if [[ -f /root/diplomacia-auth.json ]]; then
  if [[ "${TRANSFER_RACE_LEVEL_UP:-}" == "1" ]]; then
    python3 "$ROOT/scripts/transfer_race_probe.py" --level-up >/dev/null
  else
    python3 "$ROOT/scripts/transfer_race_probe.py" >/dev/null
  fi
  python3 - "$ROOT/output/reverse/transfer_race_probe.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d["status"] in ("skipped", "ok"), f"unexpected status: {d.get('status')}"
if d["status"] == "ok":
    assert not d.get("race_exploit"), "transfer race exploit detected"
print("transfer_race_probe OK:", d["status"])
PY
else
  echo "SKIP transfer_race_probe (no /root/diplomacia-auth.json)"
fi

echo "VERIFY-AUDIT OK"
