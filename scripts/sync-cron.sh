#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
exec python3 github_sync.py
