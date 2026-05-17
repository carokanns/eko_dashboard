#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_URL="http://127.0.0.1:3000"

if [[ "${DASHBOARD_SKIP_AWAKE:-0}" != "1" && "${DASHBOARD_KEEP_AWAKE:-1}" != "0" ]]; then
  exec "$ROOT_DIR/scripts/run-dashboard-awake.sh"
fi

cd "$ROOT_DIR"

./scripts/run-dev.sh

# Wait for the frontend to become reachable before opening the app.
for _ in {1..180}; do
  if curl -fsS "$APP_URL" >/dev/null 2>&1; then
    if command -v flatpak >/dev/null 2>&1 && flatpak info com.brave.Browser >/dev/null 2>&1; then
      flatpak run com.brave.Browser "$APP_URL" >/dev/null 2>&1 &
    else
      xdg-open "$APP_URL" >/dev/null 2>&1 &
    fi
    exit 0
  fi
  sleep 1
done

if command -v notify-send >/dev/null 2>&1; then
  notify-send "Ekonomi Dashboard" "Tjansterna startade, men frontend svarade inte inom 180 sekunder."
fi

exit 1
