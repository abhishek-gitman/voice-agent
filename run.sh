#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env — add DEEPGRAM_API_KEY and GEMINI_API_KEY (see runtime/bot.py)."
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv and installing dependencies..."
  python3 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r requirements.txt
fi

# Mac: mic/speaker need PortAudio + PyAudio (pipecat-ai[local])
if ! .venv/bin/python -c "import pyaudio" 2>/dev/null; then
  if [[ "$(uname)" == "Darwin" ]] && command -v brew >/dev/null; then
    if ! brew list portaudio &>/dev/null; then
      echo "Installing PortAudio (required for microphone on Mac)..."
      brew install portaudio
    fi
  fi
  echo "Installing PyAudio for local voice..."
  .venv/bin/pip install 'pipecat-ai[local]==1.3.0'
fi

exec .venv/bin/python -m runtime.bot --config config/agent_runtime.json
