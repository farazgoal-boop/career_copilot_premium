"""Server-side ElevenLabs speech synthesis.

The ElevenLabs API key never reaches the browser -- same rule as the
Mistral key (desktop_app/mistral_setup.py). The Flask route calls this
module and streams the resulting audio back to the client; if no key is
configured the client falls back to the browser's own Web Speech
Synthesis, which needs no server round-trip at all.
"""

from __future__ import annotations

import json
from urllib import error, request

from .voice_prefs import DEFAULT_SPEED, DEFAULT_VOICE_ID

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
# Multilingual model so this is ready for Step 3.2's language selection
# without another provider round-trip change.
TTS_MODEL_ID = "eleven_multilingual_v2"
AUDIO_MIME_TYPE = "audio/mpeg"
MAX_TEXT_LENGTH = 2000


class SpeechSynthesisError(RuntimeError):
    """Raised when ElevenLabs synthesis fails -- caller should fall back to browser TTS."""


def synthesize_speech(
    text: str,
    api_key: str,
    voice_id: str = DEFAULT_VOICE_ID,
    speed: float = DEFAULT_SPEED,
    timeout_seconds: float = 30.0,
) -> bytes:
    """Return MP3 audio bytes for the given text, or raise SpeechSynthesisError."""
    clean_text = text.strip()
    if not clean_text:
        raise SpeechSynthesisError("No text to speak.")
    if len(clean_text) > MAX_TEXT_LENGTH:
        clean_text = clean_text[:MAX_TEXT_LENGTH]
    if not api_key:
        raise SpeechSynthesisError("ElevenLabs API key is not configured.")

    payload = {
        "text": clean_text,
        "model_id": TTS_MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": speed,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)
    http_request = request.Request(
        url,
        data=body,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": AUDIO_MIME_TYPE,
        },
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            audio_bytes = response.read()
    except error.HTTPError as http_error:
        detail = ""
        try:
            detail = http_error.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        if http_error.code in {401, 403}:
            raise SpeechSynthesisError("Invalid ElevenLabs API key.") from http_error
        raise SpeechSynthesisError(
            f"ElevenLabs API error ({http_error.code}). {detail}".strip()
        ) from http_error
    except (OSError, TimeoutError, error.URLError) as exc:
        raise SpeechSynthesisError(f"Could not reach ElevenLabs API: {exc}") from exc

    if not audio_bytes:
        raise SpeechSynthesisError("ElevenLabs returned no audio.")
    return audio_bytes
