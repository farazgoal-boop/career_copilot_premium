#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

OS_NAME="$(uname -s)"
echo "Career Copilot Premium launcher ($OS_NAME)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed."
  if [ "$OS_NAME" = "Darwin" ]; then
    echo "Run: ./install_mac.sh"
  else
    echo "Run: ./install_linux.sh"
  fi
  exit 1
fi

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example."
  else
    echo "Missing .env and .env.example in $(pwd)"
    exit 1
  fi
fi

if ! grep -q '^MISTRAL_API_KEY=.\+' .env 2>/dev/null; then
  echo "MISTRAL_API_KEY is missing in .env"
  echo "Get a free key at https://console.mistral.ai/"
  echo "Paste it into .env or enter it in the first-run setup window."
fi

if [ "$OS_NAME" = "Darwin" ]; then
  if ! system_profiler SPAudioDataType 2>/dev/null | grep -qi blackhole; then
    echo "Tip: install BlackHole for Zoom/Meet audio capture: brew install blackhole-2ch"
  fi
elif [ "$OS_NAME" = "Linux" ]; then
  if command -v pactl >/dev/null 2>&1; then
    pactl load-module module-loopback latency_msec=1 2>/dev/null || true
  fi
fi

export CAREER_COPILOT_PORTABLE=1
PORT="${DASHBOARD_PORT:-5000}"

(
  sleep 4
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:${PORT}" >/dev/null 2>&1 || true
  elif [ "$OS_NAME" = "Darwin" ]; then
    open "http://127.0.0.1:${PORT}" >/dev/null 2>&1 || true
  fi
) &

python3 premium_launcher.py
