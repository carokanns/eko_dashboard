#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  rm -f "$RUN_DIR/backend.pid" "$RUN_DIR/frontend.pid"
}

trap cleanup EXIT INT TERM

mkdir -p "$RUN_DIR"

"$ROOT_DIR/scripts/run-backend.sh" &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$RUN_DIR/backend.pid"

"$ROOT_DIR/scripts/run-frontend.sh" &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$RUN_DIR/frontend.pid"

wait "$BACKEND_PID" "$FRONTEND_PID"
