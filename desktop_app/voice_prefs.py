"""Voice-output preferences: which ElevenLabs voice + speaking rate to use.

Mirrors the JSON-prefs pattern in desktop_app/language_config.py rather than
the .env pattern in elevenlabs_setup.py, since these are UI choices, not a
secret.
"""

from __future__ import annotations

import json
from pathlib import Path

from runtime_paths import cache_root

# (label, ElevenLabs voice_id) — curated subset of ElevenLabs' premade voice
# library, not user-editable yet.
VOICE_OPTIONS: list[tuple[str, str]] = [
    ("Rachel (Natural)", "21m00Tcm4TlvDq8ikWAM"),
    ("Bella (Warm)", "EXAVITQu4vr4xnSDxMaL"),
    ("Antoni (Confident)", "ErXwobaYiN019PkySvjV"),
    ("Josh (Deep)", "TxGEqnHWrfWFTfGW9XjX"),
]

# (label, rate multiplier) — used both as ElevenLabs voice_settings.speed and
# as the browser SpeechSynthesisUtterance.rate fallback.
SPEED_OPTIONS: list[tuple[str, float]] = [
    ("Slow", 0.85),
    ("Normal", 1.0),
    ("Fast", 1.15),
]

DEFAULT_VOICE_ID = VOICE_OPTIONS[0][1]
DEFAULT_SPEED = 1.0


def _prefs_path() -> Path:
    return cache_root() / "voice_prefs.json"


def load_voice_prefs() -> dict[str, object]:
    path = _prefs_path()
    if not path.is_file():
        return {"voice_id": DEFAULT_VOICE_ID, "speed": DEFAULT_SPEED}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"voice_id": DEFAULT_VOICE_ID, "speed": DEFAULT_SPEED}
    voice_id = str(payload.get("voice_id", DEFAULT_VOICE_ID) or DEFAULT_VOICE_ID)
    speed = payload.get("speed", DEFAULT_SPEED)
    return {
        "voice_id": _normalize_voice_id(voice_id),
        "speed": _normalize_speed(speed),
    }


def save_voice_prefs(voice_id: str, speed: float) -> dict[str, object]:
    prefs = {
        "voice_id": _normalize_voice_id(voice_id),
        "speed": _normalize_speed(speed),
    }
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    return prefs


def voice_label_for_id(voice_id: str) -> str:
    normalized = _normalize_voice_id(voice_id)
    for label, value in VOICE_OPTIONS:
        if value == normalized:
            return label
    return normalized


def _normalize_voice_id(value: str) -> str:
    voice_id = str(value or "").strip()
    valid = {item[1] for item in VOICE_OPTIONS}
    return voice_id if voice_id in valid else DEFAULT_VOICE_ID


def _normalize_speed(value: object) -> float:
    try:
        speed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_SPEED
    valid = {item[1] for item in SPEED_OPTIONS}
    return speed if speed in valid else DEFAULT_SPEED
