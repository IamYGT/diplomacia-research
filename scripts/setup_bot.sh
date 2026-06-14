#!/usr/bin/env bash
# Diplomacia bot — kurulum (proxy Tor, PM2)
set -euo pipefail

REPO="${REPO:-/root/diplomacia-research}"
BOT="$REPO/bot"
cd "$BOT"

echo "=== venv ==="
python3 -m venv .venv
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

echo "=== engagement sync ==="
python3 "$REPO/scripts/sync_engagement.py"

echo "=== .env ==="
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "⚠️  .env oluşturuldu — TELEGRAM_BOT_TOKEN ve TELEGRAM_ADMIN_IDS doldur"
fi

echo "=== DB init + mevcut JWT ==="
python3 -c "
from diplomacy_bot.store import init_db, bootstrap_legacy, list_accounts
init_db()
bootstrap_legacy()
print('Hesaplar:', [(a.name, a.proxy_id, a.autofarm) for a in list_accounts()])
"

echo "=== Tor proxy test ==="
COOKIE=$(xxd -p -c 256 /var/run/tor/control.authcookie 2>/dev/null || true)
if [[ -n "$COOKIE" ]]; then
  printf 'AUTHENTICATE %s\r\nSIGNAL NEWNYM\r\nQUIT\r\n' "$COOKIE" | nc -U -w 3 /var/run/tor/control >/dev/null 2>&1 || true
  TOR_IP=$(curl -s --max-time 12 --proxy socks5h://127.0.0.1:9050 https://api.ipify.org || echo fail)
  DIRECT_IP=$(curl -s --max-time 8 https://api.ipify.org || echo fail)
  echo "Direct: $DIRECT_IP | Tor: $TOR_IP"
else
  echo "Tor cookie yok — proxy devre dışı"
fi

echo ""
echo "Sonraki adımlar:"
echo "  1. bot/data/tokens.json oluştur (tokens.template.json örnek)"
echo "  2. python3 $REPO/scripts/import_tokens.py"
echo "  3. .env içine TELEGRAM_BOT_TOKEN + TELEGRAM_ADMIN_IDS"
echo "  4. pm2 start ecosystem.config.cjs"
