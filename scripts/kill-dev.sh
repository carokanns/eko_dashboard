#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_NEXT_PATTERN="$ROOT_DIR/frontend/node_modules/.bin/next dev"

cd "$ROOT_DIR"
docker compose down
pkill -f "$LOCAL_NEXT_PATTERN" >/dev/null 2>&1 || true
