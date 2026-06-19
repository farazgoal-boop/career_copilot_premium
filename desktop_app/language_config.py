"""Listen/reply language preferences for live STT and Mistral answers."""

from __future__ import annotations

import json
from pathlib import Path

from runtime_paths import cache_root


LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("English", "en-US"),
    ("Arabic", "ar-SA"),
    ("Urdu", "ur-PK"),
    ("French", "fr-FR"),
    ("Spanish", "es-ES"),
    ("Hindi", "hi-IN"),
    ("Turkish", "tr-TR"),
]

DEFAULT_LISTEN = "en-US"
DEFAULT_REPLY = "en-US"


def _prefs_path() -> Path:
    return cache_root() / "language_prefs.json"


def load_language_prefs() -> dict[str, str]:
    path = _prefs_path()
    if not path.is_file():
        return {"listen_language": DEFAULT_LISTEN, "reply_language": DEFAULT_REPLY}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"listen_language": DEFAULT_LISTEN, "reply_language": DEFAULT_REPLY}
    listen = str(payload.get("listen_language", DEFAULT_LISTEN) or DEFAULT_LISTEN)
    reply = str(payload.get("reply_language", DEFAULT_REPLY) or DEFAULT_REPLY)
    return {"listen_language": _normalize_code(listen), "reply_language": _normalize_code(reply)}


def save_language_prefs(listen_language: str, reply_language: str) -> dict[str, str]:
    prefs = {
        "listen_language": _normalize_code(listen_language),
        "reply_language": _normalize_code(reply_language),
    }
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    return prefs


def get_listen_language_code() -> str:
    return load_language_prefs()["listen_language"]


def get_reply_language_code() -> str:
    return load_language_prefs()["reply_language"]


def language_label_for_code(code: str) -> str:
    normalized = _normalize_code(code)
    for label, value in LANGUAGE_OPTIONS:
        if value == normalized:
            return label
    return normalized


def _normalize_code(value: str) -> str:
    code = str(value or "").strip()
    valid = {item[1] for item in LANGUAGE_OPTIONS}
    return code if code in valid else DEFAULT_LISTEN
