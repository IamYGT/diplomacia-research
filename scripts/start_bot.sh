#!/usr/bin/env bash
# Bot başlat — .env dolu olmalı
set -euo pipefail
cd /root/diplomacia-research/bot
source .venv/bin/activate
set -a
source .env
set +a
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || "$TELEGRAM_BOT_TOKEN" == "your_bot_token_here" ]]; then
  echo "TELEGRAM_BOT_TOKEN eksik — bot/.env düzenle"
  exit 1
fi
exec pm2 start ecosystem.config.cjs --update-env
pm2 save 2>/dev/null || true
pm2 status diplomacy-ygt-bot
