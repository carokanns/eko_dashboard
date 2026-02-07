#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

"$ROOT_DIR/scripts/run-backend.sh" &
BACKEND_PID=$!

"$ROOT_DIR/scripts/run-frontend.sh" &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
