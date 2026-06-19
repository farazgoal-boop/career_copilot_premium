#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================================"
echo " Career Copilot Premium — macOS setup"
echo "============================================================"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
    echo "Install Homebrew manually from https://brew.sh then re-run this script."
    exit 1
  }
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

echo "[1/4] Installing Python and BlackHole audio driver..."
brew install python@3.11 blackhole-2ch || true

echo "[2/4] Installing Python packages..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[3/4] Preparing .env..."
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your MISTRAL_API_KEY."
fi

echo "[4/4] Checking BlackHole audio device..."
if system_profiler SPAudioDataType 2>/dev/null | grep -qi blackhole; then
  echo "✅ BlackHole detected for call audio capture."
else
  echo "⚠️  BlackHole not detected yet. After install, reboot or set BlackHole as output in Audio MIDI Setup."
  echo "   Install command: brew install blackhole-2ch"
fi

echo ""
echo "✅ Setup complete!"
echo "Next steps:"
echo "  1. Add MISTRAL_API_KEY to .env (or enter it in the first-run setup window)"
echo "  2. Run: ./START_PREMIUM.sh"
echo "  3. Press F2 during interviews to capture questions"
