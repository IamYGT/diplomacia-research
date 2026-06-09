#!/usr/bin/env bash
# Smoke verify: interactive guide static assets + meta JSON + optional live HTTP.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GUIDE="$ROOT/public/guide"
META="$ROOT/public/data/guide-meta.json"
BASE_URL="${GUIDE_BASE_URL:-https://diplomacia.ygtlabs.ai}"

echo "== verify-guide =="
echo "ROOT=$ROOT"
echo "BASE_URL=$BASE_URL"

fail() { echo "FAIL: $*" >&2; exit 1; }

# Static files
test -f "$GUIDE/index.html" || fail "missing guide/index.html"
test -f "$GUIDE/guide.css" || fail "missing guide/guide.css"
test -f "$GUIDE/guide.js" || fail "missing guide/guide.js"
test -f "$META" || fail "missing public/data/guide-meta.json"

# Required section anchors
for id in hero architecture core-loop resources day1 farm-loop calculator checklist api endgame; do
  grep -q "id=\"${id}\"" "$GUIDE/index.html" || fail "missing section id=$id"
done

# Meta schema + calculator contract (144 cycles × gold_per_work)
python3 - "$META" <<'PY'
import json, sys
path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
assert d["economy"]["gold_per_work"] == 2404
assert d["world"]["total_players"] >= 4000
assert d["quests"]["work_1"]["reward_gold"] == 5000
assert isinstance(d.get("checklist"), list) and len(d["checklist"]) >= 6
cycles = 144
gold = d["economy"]["gold_per_work"]
assert cycles * gold == 346176, (cycles, gold, cycles * gold)
print("meta OK:", d["updated_at"], "gold_per_work=", gold)
PY

# Hub links to guide
grep -q '/guide/' "$ROOT/public/index.html" || fail "hub index missing /guide/ link"
grep -q '/guide/' "$ROOT/scripts/build_public_site.py" || fail "build_public_site missing /guide/ link"

# Optional HTTP (skip if offline)
if command -v curl >/dev/null 2>&1; then
  code=$(curl -sS --http1.1 -o /dev/null -w '%{http_code}' "$BASE_URL/guide/" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    curl -sSf "$BASE_URL/guide/" | grep -q 'İnteraktif Ustalık' || fail "guide HTML missing title"
    curl -sSf "$BASE_URL/data/guide-meta.json" | python3 -c "import json,sys; json.load(sys.stdin)"
    echo "HTTP OK: /guide/ 200, guide-meta.json 200"
  else
    echo "WARN: HTTP $code for $BASE_URL/guide/ (static checks passed)"
  fi
fi

echo "VERIFY OK"
