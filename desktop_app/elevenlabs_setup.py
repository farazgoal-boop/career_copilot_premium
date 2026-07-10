"""ElevenLabs API key storage and validation — optional voice-output enhancement.

Storage follows the same plaintext .env pattern as MISTRAL_API_KEY
(desktop_app/mistral_setup.py) rather than encryption, for consistency with
the rest of the app's key handling.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import error, request

from runtime_paths import load_env_file, primary_env_file_path

ELEVENLABS_USER_URL = "https://api.elevenlabs.io/v1/user"
ELEVENLABS_CONSOLE_URL = "https://elevenlabs.io/"


def elevenlabs_api_key() -> str:
    load_env_file()
    return os.environ.get("ELEVENLABS_API_KEY", "").strip()


def has_elevenlabs_api_key() -> bool:
    return bool(elevenlabs_api_key())


def save_elevenlabs_api_key(api_key: str) -> Path:
    key = api_key.strip()
    if not key:
        raise ValueError("API key cannot be empty.")
    target = primary_env_file_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PermissionError(
            f"Could not create settings folder at {target.parent}. ({exc})"
        ) from exc
    lines: list[str] = []
    if target.is_file():
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.strip().startswith("ELEVENLABS_API_KEY="):
            new_lines.append(f"ELEVENLABS_API_KEY={key}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(f"ELEVENLABS_API_KEY={key}")
    try:
        target.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot write API key to {target}. Run as user (not Program Files). "
            "The app will save to your user AppData folder automatically."
        ) from exc
    os.environ["ELEVENLABS_API_KEY"] = key
    return target


def validate_elevenlabs_api_key(api_key: str | None = None) -> tuple[bool, str]:
    key = (api_key or elevenlabs_api_key()).strip()
    if not key:
        return False, "API key is missing."
    try:
        http_request = request.Request(
            ELEVENLABS_USER_URL,
            headers={"xi-api-key": key},
            method="GET",
        )
        with request.urlopen(http_request, timeout=12.0) as response:
            if response.status != 200:
                return False, f"ElevenLabs API returned status {response.status}."
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            return False, "Unexpected ElevenLabs API response."
        return True, "ElevenLabs Connected"
    except error.HTTPError as http_error:
        if http_error.code in {401, 403}:
            return False, "Invalid ElevenLabs API key."
        return False, f"ElevenLabs API error ({http_error.code})."
    except (OSError, TimeoutError, ValueError, error.URLError) as exc:
        return False, f"Could not reach ElevenLabs API: {exc}"
