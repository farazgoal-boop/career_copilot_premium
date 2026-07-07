"""Translate an already-generated answer before speaking it aloud.

Only needed when "speak answers to caller in" resolves to a different
language than the answer was generated in (desktop_app/language_config.py's
speak_language vs reply_language) -- ElevenLabs/browser speech synthesis
reads text aloud in whatever language it's written in, it doesn't translate
on its own.
"""

from __future__ import annotations

import json
from urllib import error, request

from .mistral_setup import mistral_api_key

TRANSLATE_MODEL = "mistral-small-latest"
TRANSLATE_BASE_URL = "https://api.mistral.ai/v1/chat/completions"


class TranslationError(RuntimeError):
    """Raised when translation fails -- caller should fall back to the original text."""


def translate_text(
    text: str,
    target_language_label: str,
    source_language_label: str | None = None,
    timeout_seconds: float = 15.0,
) -> str:
    """Return `text` translated into target_language_label, or raise TranslationError."""
    clean_text = text.strip()
    if not clean_text:
        raise TranslationError("No text to translate.")

    api_key = mistral_api_key()
    if not api_key:
        raise TranslationError("Mistral API key is not configured — add one in Settings.")

    source_clause = f" from {source_language_label}" if source_language_label else ""
    prompt = (
        f"Translate the following text{source_clause} into {target_language_label}. "
        "Keep the same tone and meaning -- this is a spoken reply in a live call, so keep it "
        "natural to say aloud, not a literal word-for-word translation.\n\n"
        f"Text:\n{clean_text}\n\n"
        "Respond with ONLY a JSON object in this exact shape, no other text:\n"
        '{"translated_text": "..."}'
    )
    payload = {
        "model": TRANSLATE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        TRANSLATE_BASE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as http_error:
        raise TranslationError(f"Mistral translation API error ({http_error.code}).") from http_error
    except (OSError, TimeoutError, ValueError, error.URLError) as exc:
        raise TranslationError(f"Could not reach Mistral translation API: {exc}") from exc

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise TranslationError("Mistral translation response did not include choices.")
    message = choices[0].get("message", {})
    content = str(message.get("content", "")).strip()
    if not content:
        raise TranslationError("Mistral translation response did not include content.")

    try:
        parsed = json.loads(content)
    except ValueError:
        # Model didn't return clean JSON -- the raw content is still usable as a translation.
        return content

    translated = str(parsed.get("translated_text", "") or "").strip()
    return translated or content
