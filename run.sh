#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 run.py "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python run.py "$@"
fi

echo "Python 3.9+ is required but was not found on PATH." >&2
exit 1
