"""Fallback actions shown during preparation and live interview mode."""

from __future__ import annotations


def build_fallback_plan() -> dict[str, str]:
    return {
        "simple": "Need simpler words",
        "alternatives": "Give me 2 alternatives",
        "emergency": "That's an interesting perspective. Let me think about that.",
        "clarifying_question": "Could you help me understand what specific aspect you're asking about?",
    }