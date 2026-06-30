#!/bin/sh
# Git pre-commit hook kur — API sözleşme kontrolü
set -e
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "git repo değil — hook kurulmadı" >&2
  exit 1
}
HOOK_SRC="$ROOT/bot/scripts/githooks/pre-commit"
HOOK_DST="$ROOT/.git/hooks/pre-commit"
chmod +x "$HOOK_SRC"
cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"
echo "Kuruldu: $HOOK_DST"
echo "Kaldırmak için: rm $HOOK_DST"
