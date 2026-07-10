"""Pre-session company/client research briefing generation.

LLM-generated background (Mistral, JSON mode) from the model's training
knowledge -- NOT a live web lookup. There is no browsing/search integration
in this codebase, so the briefing may be outdated or incomplete for smaller
or fast-moving companies; the caveat field is surfaced in the UI for this
reason rather than presented as verified current fact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from urllib import error, request

from .mistral_setup import mistral_api_key
from .session_types import DEFAULT_SESSION_TYPE, normalize_session_type

RESEARCH_MODEL = "mistral-small-latest"
RESEARCH_BASE_URL = "https://api.mistral.ai/v1/chat/completions"

_RESEARCH_CAVEAT = (
    "Generated from general knowledge, not a live lookup -- verify anything "
    "time-sensitive (recent news, leadership, funding) before relying on it."
)

_RESEARCH_FRAMING: dict[str, dict[str, str]] = {
    "job_interview": {"noun": "interview prep briefing", "questions_label": "smart questions to ask the interviewer"},
    "client_presentation": {"noun": "client briefing", "questions_label": "smart questions to ask the client"},
    "product_demo": {"noun": "prospect briefing", "questions_label": "smart questions to ask the audience"},
    "team_meeting": {"noun": "meeting context briefing", "questions_label": "smart questions to raise in the meeting"},
    "sales_call": {"noun": "prospect briefing", "questions_label": "smart questions to ask the prospect"},
}


def _framing_for(session_type: str) -> dict[str, str]:
    return _RESEARCH_FRAMING.get(normalize_session_type(session_type), _RESEARCH_FRAMING["job_interview"])


@dataclass
class CompanyResearchResult:
    company_name: str
    role_title: str
    overview: str
    focus_areas: list[str]
    culture_values: list[str]
    smart_questions_to_ask: list[str]
    caveat: str


def generate_company_research(
    company_name: str,
    role_title: str = "",
    session_type: str = DEFAULT_SESSION_TYPE,
    timeout_seconds: float = 25.0,
) -> CompanyResearchResult:
    """Generate a company/client research briefing ahead of a session.

    Raises RuntimeError if the API key is missing or the call fails --
    callers should catch this and degrade gracefully (e.g. skip storing a
    briefing rather than blocking session start).
    """
    company = company_name.strip()
    if not company:
        raise RuntimeError("Company name is required to generate research.")

    api_key = mistral_api_key()
    if not api_key:
        raise RuntimeError("Mistral API key is not configured — add one in Settings.")

    framing = _framing_for(session_type)
    prompt = _build_research_prompt(company, role_title.strip(), framing)

    payload = {
        "model": RESEARCH_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        RESEARCH_BASE_URL,
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
        raise RuntimeError(f"Mistral research API error ({http_error.code}).") from http_error
    except (OSError, TimeoutError, ValueError, error.URLError) as exc:
        raise RuntimeError(f"Could not reach Mistral research API: {exc}") from exc

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Mistral research response did not include choices.")
    message = choices[0].get("message", {})
    content = str(message.get("content", "")).strip()
    if not content:
        raise RuntimeError("Mistral research response did not include content.")

    return _parse_research_response(content, company, role_title.strip())


def _build_research_prompt(company_name: str, role_title: str, framing: dict[str, str]) -> str:
    role_context = f" for a {role_title} {('role' if role_title else '')}".rstrip() if role_title else ""
    return (
        f"You are preparing a concise {framing['noun']} about \"{company_name}\"{role_context}.\n"
        "Draw on what you know about this company (or, if you don't recognize the name, give sensible "
        "general guidance for a company of that type/industry based on the name alone).\n"
        "Respond with ONLY a JSON object in this exact shape, no other text:\n"
        "{"
        '"overview": "2-3 sentence snapshot of the company/industry/what they do", '
        '"focus_areas": ["3-4 likely areas of focus or priorities for this session"], '
        '"culture_values": ["3-4 stated or likely values/culture points"], '
        f'"smart_questions_to_ask": ["3-4 {framing["questions_label"]}"]'
        "}"
    )


def _parse_research_response(content: str, company_name: str, role_title: str) -> CompanyResearchResult:
    try:
        payload = json.loads(content)
    except ValueError:
        return CompanyResearchResult(
            company_name=company_name,
            role_title=role_title,
            overview=content,
            focus_areas=[],
            culture_values=[],
            smart_questions_to_ask=[],
            caveat=_RESEARCH_CAVEAT,
        )

    def _string_list(key: str) -> list[str]:
        raw = payload.get(key, [])
        return [str(item).strip() for item in raw if str(item).strip()] if isinstance(raw, list) else []

    return CompanyResearchResult(
        company_name=company_name,
        role_title=role_title,
        overview=str(payload.get("overview", "") or "").strip(),
        focus_areas=_string_list("focus_areas"),
        culture_values=_string_list("culture_values"),
        smart_questions_to_ask=_string_list("smart_questions_to_ask"),
        caveat=_RESEARCH_CAVEAT,
    )


def company_research_to_dict(result: CompanyResearchResult) -> dict[str, object]:
    return asdict(result)
