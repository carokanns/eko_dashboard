#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

cd "$BACKEND_DIR"

if [[ -x .venv/bin/python ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="python"
fi

exec env PYTHONFAULTHANDLER=1 "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning --no-access-log
