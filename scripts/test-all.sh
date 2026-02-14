#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

printf "Running docs/shell sync checks...\n"
(
  cd "$ROOT_DIR"
  ./scripts/check-readme-sync.sh
)

printf "Running backend tests...\n"
(
  cd "$ROOT_DIR/backend"
  if [[ -x .venv/bin/python ]]; then
    .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
    .venv/bin/python -m pytest
  else
    python -m pip install -r requirements.txt -r requirements-dev.txt
    python -m pytest
  fi
)

printf "Running frontend tests...\n"
(
  cd "$ROOT_DIR/frontend"
  npm install
  npm run test
)

printf "All tests completed.\n"
