#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="${1:-}"

cd "$ROOT_DIR"

echo "[1/3] Pull latest from origin/master"
git pull origin master

echo "[2/3] Rebuild and restart with Docker Compose"
docker compose up -d --build

echo "[3/3] Show latest commit"
LATEST_LINE="$(git log -1 --oneline)"
echo "$LATEST_LINE"

if [[ -n "$EXPECTED_COMMIT" ]]; then
  LATEST_HASH="${LATEST_LINE%% *}"
  if [[ "$LATEST_HASH" != "$EXPECTED_COMMIT" ]]; then
    echo "ERROR: Expected commit $EXPECTED_COMMIT but got $LATEST_HASH" >&2
    exit 1
  fi
  echo "Commit check OK: $LATEST_HASH"
fi
