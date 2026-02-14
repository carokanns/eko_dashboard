#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="${1:-}"
USAGE_ONE="./scripts/update-remote-docker.sh"
USAGE_TWO="./scripts/update-remote-docker.sh <full-commit-hash>"

if [[ "$EXPECTED_COMMIT" == "-h" || "$EXPECTED_COMMIT" == "--help" ]]; then
  echo "Usage:"
  echo "  $USAGE_ONE"
  echo "  $USAGE_TWO"
  exit 0
fi

cd "$ROOT_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is not installed." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Working tree has local changes. Commit/stash before deploy." >&2
  exit 1
fi

echo "[1/5] Fetch latest from origin/master"
git fetch origin master

REMOTE_HASH="$(git rev-parse origin/master)"
if [[ -n "$EXPECTED_COMMIT" && "$REMOTE_HASH" != "$EXPECTED_COMMIT" ]]; then
  echo "ERROR: Expected remote commit $EXPECTED_COMMIT but origin/master is $REMOTE_HASH" >&2
  exit 1
fi

echo "[2/5] Fast-forward local master"
git pull --ff-only origin master

echo "[3/5] Rebuild and restart with Docker Compose"
docker compose up -d --build

echo "[4/5] Verify deployed commit"
LATEST_HASH="$(git rev-parse HEAD)"
echo "Deployed commit: $LATEST_HASH"

echo "[5/5] Done"
