"""Post-session meeting summary generation from the transcript log.

Built from transcript_log only (questions heard + Mistral's suggested
answers) -- NOT a verified two-way transcript, since the user's own spoken
words are never captured, only what Mistral suggested they say in the
moment. The prompt is explicit about this so the model summarizes honestly
rather than presenting it as a verbatim record.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, request

from .mistral_setup import mistral_api_key
from .session_types import DEFAULT_SESSION_TYPE, normalize_session_type

SUMMARY_MODEL = "mistral-small-latest"
SUMMARY_BASE_URL = "https://api.mistral.ai/v1/chat/completions"

_SUMMARY_FRAMING: dict[str, dict[str, str]] = {
    "job_interview": {"noun": "interview debrief", "recap": "how the interview went"},
    "client_presentation": {"noun": "presentation recap", "recap": "how the client presentation went"},
    "product_demo": {"noun": "demo recap", "recap": "how the product demo went"},
    "team_meeting": {"noun": "meeting minutes", "recap": "what was discussed in the meeting"},
    "sales_call": {"noun": "call recap", "recap": "how the sales call went"},
}


def _framing_for(session_type: str) -> dict[str, str]:
    return _SUMMARY_FRAMING.get(normalize_session_type(session_type), _SUMMARY_FRAMING["job_interview"])


@dataclass
class MeetingSummaryResult:
    summary: str
    action_items: list[str]


def generate_meeting_summary(
    transcript_log: list[dict[str, object]],
    session_type: str = DEFAULT_SESSION_TYPE,
    company_name: str = "",
    role_title: str = "",
    timeout_seconds: float = 25.0,
) -> MeetingSummaryResult:
    """Summarize a session's transcript_log into a recap + action items.

    Raises RuntimeError if the API key is missing or the call fails --
    callers should catch this and degrade gracefully (e.g. skip storing a
    summary rather than blocking session end).
    """
    if not transcript_log:
        return MeetingSummaryResult(summary="", action_items=[])

    api_key = mistral_api_key()
    if not api_key:
        raise RuntimeError("Mistral API key is not configured — add one in Settings.")

    framing = _framing_for(session_type)
    prompt = _build_summary_prompt(transcript_log, framing, company_name, role_title)

    payload = {
        "model": SUMMARY_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        SUMMARY_BASE_URL,
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
        raise RuntimeError(f"Mistral summary API error ({http_error.code}).") from http_error
    except (OSError, TimeoutError, ValueError, error.URLError) as exc:
        raise RuntimeError(f"Could not reach Mistral summary API: {exc}") from exc

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Mistral summary response did not include choices.")
    message = choices[0].get("message", {})
    content = str(message.get("content", "")).strip()
    if not content:
        raise RuntimeError("Mistral summary response did not include content.")

    return _parse_summary_response(content)


def _build_summary_prompt(
    transcript_log: list[dict[str, object]],
    framing: dict[str, str],
    company_name: str,
    role_title: str,
) -> str:
    lines: list[str] = []
    for entry in transcript_log:
        question = str(entry.get("text", "") or "").strip()
        answer = str(entry.get("answer", "") or "").strip()
        if not question:
            continue
        lines.append(f"Q: {question}")
        if answer:
            lines.append(f"Suggested reply: {answer}")
    transcript_block = "\n".join(lines)
    context = f" for {role_title} at {company_name}" if role_title or company_name else ""

    return (
        f"You are generating a {framing['noun']}{context} from a live AI-coaching session log.\n"
        "The log below shows questions the AI detected during the call and the reply it suggested "
        "to the user in the moment -- it is NOT a verified transcript of what the user actually said "
        "aloud, since they may have spoken differently. Summarize honestly on that basis; do not "
        "present suggested replies as confirmed statements.\n\n"
        f"Session log:\n{transcript_block}\n\n"
        f"Write a concise summary covering {framing['recap']}, plus a list of concrete action items "
        "implied by the discussion (follow-ups, things to send, next steps to confirm).\n"
        "Respond with ONLY a JSON object in this exact shape, no other text:\n"
        '{"summary": "...", "action_items": ["...", "..."]}'
    )


def _parse_summary_response(content: str) -> MeetingSummaryResult:
    try:
        payload = json.loads(content)
    except ValueError:
        # Model didn't return clean JSON -- fall back to the raw text as the summary.
        return MeetingSummaryResult(summary=content, action_items=[])

    summary = str(payload.get("summary", "") or "").strip()
    raw_items = payload.get("action_items", [])
    action_items = (
        [str(item).strip() for item in raw_items if str(item).strip()]
        if isinstance(raw_items, list)
        else []
    )
    return MeetingSummaryResult(summary=summary or content, action_items=action_items)
