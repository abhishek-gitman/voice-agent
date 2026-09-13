#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "Run ./run.sh once first to create .venv, or: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

echo ""
echo "  SuperVoice Studio → http://127.0.0.1:8765"
echo "  Press Ctrl+C to stop the dashboard (stops UI only; use Stop in UI for the agent)."
echo ""
(sleep 1 && open "http://127.0.0.1:8765" 2>/dev/null) &
exec .venv/bin/uvicorn studio.app:app --host 127.0.0.1 --port 8765 --reload
