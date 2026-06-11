#!/usr/bin/env bash
# Start the Agentic Investment Committee web app (Django + Channels).
#   ./start-web.sh                 -> http://127.0.0.1:8000
#   HOST=0.0.0.0 PORT=9000 ./start-web.sh
#
# .env is loaded automatically; set LLM_PROVIDER + the matching API key first.
set -euo pipefail

# Run from the project root, wherever this script is invoked from.
cd "$(dirname "$0")"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

# Prefer a project venv if present, else fall back to system python.
if [ -x "venv/Scripts/python.exe" ]; then PY="venv/Scripts/python.exe"   # Windows venv
elif [ -x "venv/bin/python" ];      then PY="venv/bin/python"            # POSIX venv
elif command -v python  >/dev/null 2>&1; then PY="python"
else PY="python3"; fi

if [ ! -f ".env" ]; then
  echo "⚠  no .env found — set LLM_PROVIDER + the matching API key first (see CLAUDE.md)." >&2
fi

echo "▶  自主投資委員會 Web  →  http://${HOST}:${PORT}   (Ctrl+C 結束)"
exec "$PY" manage.py runserver "${HOST}:${PORT}"
