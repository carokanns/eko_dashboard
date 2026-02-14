#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
README_PATH="$ROOT_DIR/README.md"
DEPLOY_SCRIPT="$ROOT_DIR/scripts/update-remote-docker.sh"

if [[ ! -f "$README_PATH" ]]; then
  echo "ERROR: README.md not found." >&2
  exit 1
fi

if [[ ! -f "$DEPLOY_SCRIPT" ]]; then
  echo "ERROR: scripts/update-remote-docker.sh not found." >&2
  exit 1
fi

usage_one="$(awk -F'"' '/^USAGE_ONE=/{print $2; exit}' "$DEPLOY_SCRIPT")"
usage_two="$(awk -F'"' '/^USAGE_TWO=/{print $2; exit}' "$DEPLOY_SCRIPT")"

if [[ -z "$usage_one" || -z "$usage_two" ]]; then
  echo "ERROR: Could not read USAGE_ONE/USAGE_TWO from deploy script." >&2
  exit 1
fi

if ! grep -Fq "\`$usage_one\`" "$README_PATH"; then
  echo "ERROR: README is missing deploy usage command: $usage_one" >&2
  exit 1
fi

if ! grep -Fq "\`$usage_two\`" "$README_PATH"; then
  echo "ERROR: README is missing deploy usage command: $usage_two" >&2
  exit 1
fi

bash -n "$DEPLOY_SCRIPT"
echo "README deploy usage is in sync with scripts/update-remote-docker.sh"
