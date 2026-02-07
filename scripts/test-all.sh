#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

printf '== Backend tests ==\n'
(
  cd "$repo_root/backend"
  if [[ -x .venv/bin/python ]]; then
    PY=.venv/bin/python
  else
    PY=python
  fi
  "$PY" -m pytest
)

printf '\n== Frontend tests ==\n'
(
  cd "$repo_root/frontend"
  npm test
)
