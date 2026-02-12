#!/usr/bin/env bash
set -euo pipefail

kill "$(cat /home/peter/Projekt/Ekonomi_dashboard/.run/backend.pid)" \
     "$(cat /home/peter/Projekt/Ekonomi_dashboard/.run/frontend.pid)"
