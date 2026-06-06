#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="${HOME}/.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser"
LOCAL_STATE="${PROFILE_DIR}/Local State"

notify() {
  local title="$1"
  local message="$2"

  if command -v zenity >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
    zenity --info --title="$title" --text="$message" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$title" "$message" >/dev/null 2>&1 || true
  else
    printf '%s\n%s\n' "$title" "$message"
  fi
}

if pgrep -af '/app/brave/brave|flatpak.*com\.brave\.Browser|bwrap.*brave' >/dev/null 2>&1; then
  notify "Brave kor" "Stang alla Brave-fonster forst. Annars kan Brave skriva over installningen nar den avslutas."
  exit 1
fi

if [[ ! -f "$LOCAL_STATE" ]]; then
  notify "Brave hittades inte" "Jag hittar inte Braves Local State-fil: ${LOCAL_STATE}"
  exit 1
fi

backup="${LOCAL_STATE}.backup-$(date +%Y%m%d-%H%M%S)"
cp "$LOCAL_STATE" "$backup"

result="$(
  node - "$LOCAL_STATE" <<'NODE'
const fs = require("fs");
const path = process.argv[2];
const raw = fs.readFileSync(path, "utf8");
const state = JSON.parse(raw);

const current = state.hardware_acceleration_mode?.enabled;
const next = current === false ? true : false;

state.hardware_acceleration_mode = {
  ...(state.hardware_acceleration_mode || {}),
  enabled: next,
};

fs.writeFileSync(path, JSON.stringify(state, null, 2) + "\n");
console.log(next ? "pa" : "av");
NODE
)"

if [[ "$result" == "av" ]]; then
  notify "Brave grafikacceleration: AV" "Hardvaruacceleration ar nu avstangd. Starta Brave igen for att laget ska galla."
else
  notify "Brave grafikacceleration: PA" "Hardvaruacceleration ar nu paslagen. Starta Brave igen for att laget ska galla."
fi
