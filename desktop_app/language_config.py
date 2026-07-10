"""Listen/reply/speak language preferences for live STT, Mistral answers, and TTS."""

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
    ("German", "de-DE"),
    ("Turkish", "tr-TR"),
]

DEFAULT_LISTEN = "en-US"
DEFAULT_REPLY = "en-US"

# Sentinel for "speak answers to caller in whatever language they spoke" --
# i.e. dynamically follow listen_language rather than a fixed code.
SPEAK_LANGUAGE_CALLER = "caller"
DEFAULT_SPEAK = SPEAK_LANGUAGE_CALLER

SPEAK_LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("Caller's language", SPEAK_LANGUAGE_CALLER),
    *LANGUAGE_OPTIONS,
]


def _prefs_path() -> Path:
    return cache_root() / "language_prefs.json"


def load_language_prefs() -> dict[str, str]:
    path = _prefs_path()
    if not path.is_file():
        return {"listen_language": DEFAULT_LISTEN, "reply_language": DEFAULT_REPLY, "speak_language": DEFAULT_SPEAK}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"listen_language": DEFAULT_LISTEN, "reply_language": DEFAULT_REPLY, "speak_language": DEFAULT_SPEAK}
    listen = str(payload.get("listen_language", DEFAULT_LISTEN) or DEFAULT_LISTEN)
    reply = str(payload.get("reply_language", DEFAULT_REPLY) or DEFAULT_REPLY)
    speak = str(payload.get("speak_language", DEFAULT_SPEAK) or DEFAULT_SPEAK)
    return {
        "listen_language": _normalize_code(listen),
        "reply_language": _normalize_code(reply),
        "speak_language": _normalize_speak_code(speak),
    }


def save_language_prefs(
    listen_language: str,
    reply_language: str,
    speak_language: str | None = None,
) -> dict[str, str]:
    """Save listen/reply/speak language prefs.

    speak_language defaults to the previously saved value (or the "caller's
    language" sentinel) when omitted, so existing callers that only know
    about listen/reply -- the Qt overlay picker, the browser-mic listen
    route -- don't need to change.
    """
    if speak_language is None:
        speak_language = load_language_prefs()["speak_language"]
    prefs = {
        "listen_language": _normalize_code(listen_language),
        "reply_language": _normalize_code(reply_language),
        "speak_language": _normalize_speak_code(speak_language),
    }
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    return prefs


def get_listen_language_code() -> str:
    return load_language_prefs()["listen_language"]


def get_reply_language_code() -> str:
    return load_language_prefs()["reply_language"]


def get_speak_language_code() -> str:
    """Resolve the "speak to caller in" preference to a concrete language code.

    Follows listen_language when the pref is set to the "caller's language"
    sentinel (the default) rather than a fixed language.
    """
    prefs = load_language_prefs()
    if prefs["speak_language"] == SPEAK_LANGUAGE_CALLER:
        return prefs["listen_language"]
    return prefs["speak_language"]


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


def _normalize_speak_code(value: str) -> str:
    code = str(value or "").strip()
    valid = {item[1] for item in SPEAK_LANGUAGE_OPTIONS}
    return code if code in valid else DEFAULT_SPEAK
