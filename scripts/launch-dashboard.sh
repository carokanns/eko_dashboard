#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_URL="http://127.0.0.1:3000"
API_HEALTH_URL="$APP_URL/api/dashboard/health"
LOCAL_NEXT_PATTERN="$ROOT_DIR/frontend/node_modules/.bin/next dev"

cd "$ROOT_DIR"

if command -v notify-send >/dev/null 2>&1; then
  notify-send "Ekonomi Dashboard" "Startar tjänsterna..."
fi

if pgrep -f "$LOCAL_NEXT_PATTERN" >/dev/null 2>&1; then
  pkill -f "$LOCAL_NEXT_PATTERN" >/dev/null 2>&1 || true
  sleep 2
fi

./scripts/run-dev.sh

open_dashboard() {
  if command -v flatpak >/dev/null 2>&1 && flatpak info com.brave.Browser >/dev/null 2>&1; then
    flatpak run com.brave.Browser "$APP_URL" >/dev/null 2>&1 &
    return 0
  fi

  if command -v gio >/dev/null 2>&1; then
    gio open "$APP_URL" >/dev/null 2>&1 &
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$APP_URL" >/dev/null 2>&1 &
    return 0
  fi

  return 1
}

for _ in {1..180}; do
  if curl -fsS "$API_HEALTH_URL" >/dev/null 2>&1; then
    open_dashboard
    if command -v notify-send >/dev/null 2>&1; then
      notify-send "Ekonomi Dashboard" "Dashboarden är igång."
    fi
    exit 0
  fi
  sleep 1
done

if command -v notify-send >/dev/null 2>&1; then
  notify-send "Ekonomi Dashboard" "Tjansterna startade, men API:t svarade inte inom 180 sekunder."
fi

exit 1
