#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================================"
echo " Career Copilot Premium — Linux setup"
echo "============================================================"

echo "[1/5] Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv portaudio19-dev pulseaudio-utils

echo "[2/5] Installing Python packages..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[3/5] Preparing .env..."
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your MISTRAL_API_KEY."
fi

echo "[4/5] Setting up PulseAudio loopback for call audio..."
if command -v pactl >/dev/null 2>&1; then
  pactl load-module module-loopback latency_msec=1 2>/dev/null || true
  echo "PulseAudio loopback module loaded (or already active)."
else
  echo "pactl not available — install pulseaudio-utils for loopback capture."
fi

echo "[5/5] Checking monitor device..."
if command -v pactl >/dev/null 2>&1 && pactl list short sources 2>/dev/null | grep -qi monitor; then
  echo "✅ PulseAudio monitor source detected for speaker capture."
else
  echo "⚠️  No monitor source found. Run: pactl load-module module-loopback"
fi

echo ""
echo "✅ Setup complete!"
echo "Next steps:"
echo "  1. Add MISTRAL_API_KEY to .env"
echo "  2. Run: ./START_PREMIUM.sh"
echo "  3. Press F2 during interviews to capture questions"
