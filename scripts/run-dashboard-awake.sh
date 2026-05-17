#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_URL="${APP_URL:-http://127.0.0.1:3000}"

declare -a SAVED_SETTINGS=()

setting_exists() {
  local schema="$1"
  local key="$2"

  gsettings writable "$schema" "$key" >/dev/null 2>&1
}

save_setting() {
  local schema="$1"
  local key="$2"

  if setting_exists "$schema" "$key"; then
    SAVED_SETTINGS+=("$schema|$key|$(gsettings get "$schema" "$key")")
  fi
}

set_setting_if_exists() {
  local schema="$1"
  local key="$2"
  local value="$3"

  if setting_exists "$schema" "$key"; then
    gsettings set "$schema" "$key" "$value"
  fi
}

restore_settings() {
  local setting schema key value

  for setting in "${SAVED_SETTINGS[@]}"; do
    IFS="|" read -r schema key value <<< "$setting"
    if setting_exists "$schema" "$key"; then
      gsettings set "$schema" "$key" "$value"
    fi
  done

  printf "\nSkarminstallningarna ar aterstallda.\n"
}

trap restore_settings EXIT

if ! command -v gsettings >/dev/null 2>&1; then
  echo "gsettings saknas. Startar dashboard utan att andra skarminstallningar."
  exec env DASHBOARD_SKIP_AWAKE=1 "$ROOT_DIR/scripts/launch-dashboard.sh"
fi

save_setting org.cinnamon.desktop.session idle-delay
save_setting org.cinnamon.settings-daemon.plugins.power sleep-display-ac
save_setting org.cinnamon.settings-daemon.plugins.power sleep-display-battery

set_setting_if_exists org.cinnamon.desktop.session idle-delay 0
set_setting_if_exists org.cinnamon.settings-daemon.plugins.power sleep-display-ac 0
set_setting_if_exists org.cinnamon.settings-daemon.plugins.power sleep-display-battery 0

echo "Skarmen halls vaken medan dashboarden kor."
echo "Tryck Ctrl+C i den har terminalen for att aterstalla installningarna."

env DASHBOARD_SKIP_AWAKE=1 "$ROOT_DIR/scripts/launch-dashboard.sh"

while true; do
  if ! curl -fsS "$APP_URL" >/dev/null 2>&1; then
    echo "Dashboarden svarar inte langre pa $APP_URL. Avslutar och aterstaller."
    exit 0
  fi
  sleep 30
done
