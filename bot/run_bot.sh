#!/usr/bin/env bash
# PM2 wrapper — Python çökünce Telegram'a verbose bildirim + crash loop uyarısı
set -uo pipefail
cd "$(dirname "$0")"
BOT_DIR="$(pwd)"
ERR_LOG="${HOME}/.pm2/logs/diplomacy-ygt-bot-error-0.log"
PY="${BOT_DIR}/.venv/bin/python3"
NOTIFY="${BOT_DIR}/scripts/telegram_crash_notify.py"
STATE_DIR="${BOT_DIR}/data"
RESTART_LOG="${STATE_DIR}/pm2_restart_times.txt"
mkdir -p "$STATE_DIR"

"${PY}" main.py
EXIT=$?

if [[ $EXIT -ne 0 ]]; then
  TAIL=""
  [[ -f "$ERR_LOG" ]] && TAIL="$(tail -n 40 "$ERR_LOG" 2>/dev/null || true)"
  NOW=$(date +%s)
  WINDOW=600
  MAX_IN_WINDOW=5
  echo "$NOW" >> "$RESTART_LOG"
  CUTOFF=$((NOW - WINDOW))
  if [[ -f "$RESTART_LOG" ]]; then
    awk -v c="$CUTOFF" '$1 >= c' "$RESTART_LOG" > "${RESTART_LOG}.tmp" 2>/dev/null \
      && mv "${RESTART_LOG}.tmp" "$RESTART_LOG"
    COUNT=$(wc -l < "$RESTART_LOG" | tr -d ' ')
    if [[ "${COUNT:-0}" -ge "$MAX_IN_WINDOW" ]]; then
      "${PY}" "$NOTIFY" \
        --exit "$EXIT" \
        --title "⚠️ PM2 crash loop (${COUNT} restart / 10dk)" \
        --detail "Bot sürekli çöküyor — log ve import kontrol et." \
        --log "$TAIL" || true
      : > "$RESTART_LOG"
    else
      "${PY}" "$NOTIFY" --exit "$EXIT" --log "$TAIL" || true
    fi
  else
    "${PY}" "$NOTIFY" --exit "$EXIT" --log "$TAIL" || true
  fi
fi
exit "$EXIT"
