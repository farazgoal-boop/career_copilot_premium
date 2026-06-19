"""Shared text and display helpers."""

from __future__ import annotations

import re

# Avoid \u0000 in source (can embed null bytes on some editors).
_CONTROL_CHARS = re.compile(
    "[" + "".join(chr(c) for c in range(0, 9))
    + chr(11) + chr(12)
    + "".join(chr(c) for c in range(14, 32))
    + "".join(chr(c) for c in range(127, 160))
    + "]"
)


def sanitize_display_text(
    value: object,
    *,
    max_length: int = 500,
    fallback: str = "",
) -> str:
    """Return human-readable UI text; drop binary/control garbage."""
    text = str(value or "")
    text = text.replace(chr(0xFFFD), " ")
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    text = _CONTROL_CHARS.sub("", text)
    text = " ".join(text.split())
    if len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."
    if not text:
        return fallback
    letters = sum(1 for ch in text if ch.isalpha())
    if len(text) >= 12 and letters < max(3, int(len(text) * 0.2)):
        return fallback
    if len(text) < 12 and letters < 2:
        return fallback
    return text
