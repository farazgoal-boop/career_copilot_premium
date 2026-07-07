"""Canonical Session Type registry (Phase 2).

session_type is a per-session choice, like company_name/role_title — not a
property of the candidate's profile. It travels with quick-start/briefing
session-start data and is stored on the session's registry entry/state, the
same way meeting_source (the call platform) already is.
"""

from __future__ import annotations

SESSION_TYPES: dict[str, str] = {
    "job_interview": "Job Interview",
    "client_presentation": "Client Presentation",
    "product_demo": "Product Demo",
    "team_meeting": "Team Meeting",
    "sales_call": "Sales Call",
}

DEFAULT_SESSION_TYPE = "job_interview"


def normalize_session_type(value: str | None) -> str:
    """Map a raw key or display label to a canonical session_type key, defaulting on anything unrecognized."""
    raw = str(value or "").strip()
    if not raw:
        return DEFAULT_SESSION_TYPE

    key = raw.casefold().replace(" ", "_").replace("-", "_")
    if key in SESSION_TYPES:
        return key

    for candidate_key, label in SESSION_TYPES.items():
        if raw.casefold() == label.casefold():
            return candidate_key

    return DEFAULT_SESSION_TYPE


def session_type_label(value: str | None) -> str:
    return SESSION_TYPES.get(normalize_session_type(value), SESSION_TYPES[DEFAULT_SESSION_TYPE])
