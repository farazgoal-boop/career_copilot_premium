"""Resume -> structured profile extraction (skills / work history / projects).

LLM-generated (Mistral, JSON mode), mirrors company_research.py's pattern:
best-effort, raises RuntimeError on any failure so the caller (onboarding)
can fall back to generic placeholder profile data rather than blocking
session creation. This is what makes the skills/work-history/projects that
strategy_generator.py and answer_builder.py rely on actually reflect the
candidate's real resume instead of hardcoded filler.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, request

from .mistral_setup import mistral_api_key

RESUME_PROFILE_MODEL = "mistral-small-latest"
RESUME_PROFILE_BASE_URL = "https://api.mistral.ai/v1/chat/completions"

# strategy_generator.py's answer templates index profile.skills[:3] and
# profile.work_history[0].achievements[0:2] directly -- an extraction that
# doesn't clear this bar is treated as a failure so the caller falls back
# to placeholder data instead of shipping a profile that crashes downstream.
_MIN_SKILLS = 3
_MIN_ACHIEVEMENTS_FOR_LATEST_JOB = 2


@dataclass
class ExtractedSkill:
    name: str
    level: str


@dataclass
class ExtractedJob:
    company_name: str
    duration: str
    achievements: list[str]


@dataclass
class ExtractedProject:
    name: str
    description: str
    technologies: list[str]
    contribution: str


@dataclass
class ResumeProfileExtraction:
    skills: list[ExtractedSkill]
    work_history: list[ExtractedJob]
    projects: list[ExtractedProject]


def extract_resume_profile(
    resume_text: str,
    target_role: str = "",
    timeout_seconds: float = 25.0,
) -> ResumeProfileExtraction:
    """Extract skills/work history/projects from raw resume text via Mistral.

    Raises RuntimeError if the API key is missing, the call fails, or the
    result doesn't have enough real content to safely replace the fallback
    placeholder profile -- callers must catch this and degrade gracefully.
    """
    text = resume_text.strip()
    if not text:
        raise RuntimeError("No resume text to extract from.")

    api_key = mistral_api_key()
    if not api_key:
        raise RuntimeError("Mistral API key is not configured.")

    prompt = _build_extraction_prompt(text, target_role.strip())
    payload = {
        "model": RESUME_PROFILE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        RESUME_PROFILE_BASE_URL,
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
        raise RuntimeError(f"Mistral resume extraction API error ({http_error.code}).") from http_error
    except (OSError, TimeoutError, ValueError, error.URLError) as exc:
        raise RuntimeError(f"Could not reach Mistral resume extraction API: {exc}") from exc

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Mistral resume extraction response did not include choices.")
    message = choices[0].get("message", {})
    content = str(message.get("content", "")).strip()
    if not content:
        raise RuntimeError("Mistral resume extraction response did not include content.")

    extraction = _parse_extraction_response(content)
    _require_minimum_content(extraction)
    return extraction


def _build_extraction_prompt(resume_text: str, target_role: str) -> str:
    role_context = f" The candidate is targeting a {target_role} role." if target_role else ""
    truncated = resume_text[:8000]
    return (
        f"Extract a structured profile from this resume text.{role_context}\n"
        "Respond with ONLY a JSON object in this exact shape, no other text:\n"
        "{"
        '"skills": [{"name": "skill name", "level": "Beginner|Intermediate|Expert"}], '
        '"work_history": [{"company_name": "...", "duration": "...", "achievements": ["specific achievement", "..."]}], '
        '"projects": [{"name": "...", "description": "...", "technologies": ["..."], "contribution": "..."}]'
        "}\n"
        "Rules:\n"
        "- List 5-10 skills actually evidenced in the resume, most relevant first.\n"
        "- List every distinct job you can find, most recent first, with 2-3 achievements each. "
        "Summarize only what's actually stated or clearly implied -- invent nothing.\n"
        "- List up to 3 notable projects if the resume names any explicitly. If it doesn't name any, synthesize "
        "exactly one project from the responsibilities/achievements of the most relevant job instead of leaving "
        "the list empty -- grounded in that job's real content, not invented.\n"
        "- If the resume text is too sparse to find real jobs, return an empty work_history list rather than inventing one.\n\n"
        f"Resume text:\n{truncated}"
    )


def _parse_extraction_response(content: str) -> ResumeProfileExtraction:
    payload = json.loads(content)

    skills: list[ExtractedSkill] = []
    for item in payload.get("skills", []) if isinstance(payload.get("skills"), list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        level = str(item.get("level", "") or "Intermediate").strip() or "Intermediate"
        skills.append(ExtractedSkill(name=name, level=level))

    work_history: list[ExtractedJob] = []
    for item in payload.get("work_history", []) if isinstance(payload.get("work_history"), list) else []:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company_name", "")).strip()
        if not company:
            continue
        achievements = [str(a).strip() for a in item.get("achievements", []) if str(a).strip()]
        if not achievements:
            continue
        work_history.append(
            ExtractedJob(
                company_name=company,
                duration=str(item.get("duration", "") or "").strip() or "Not specified",
                achievements=achievements,
            )
        )

    projects: list[ExtractedProject] = []
    for item in payload.get("projects", []) if isinstance(payload.get("projects"), list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        technologies = [str(t).strip() for t in item.get("technologies", []) if str(t).strip()]
        projects.append(
            ExtractedProject(
                name=name,
                description=str(item.get("description", "") or "").strip(),
                technologies=technologies,
                contribution=str(item.get("contribution", "") or "").strip(),
            )
        )

    return ResumeProfileExtraction(skills=skills, work_history=work_history, projects=projects)


def _require_minimum_content(extraction: ResumeProfileExtraction) -> None:
    if len(extraction.skills) < _MIN_SKILLS:
        raise RuntimeError("Resume extraction did not find enough distinct skills.")
    if not extraction.work_history:
        raise RuntimeError("Resume extraction did not find any work history.")
    if len(extraction.work_history[0].achievements) < _MIN_ACHIEVEMENTS_FOR_LATEST_JOB:
        raise RuntimeError("Resume extraction did not find enough achievements for the most recent job.")
    if not extraction.projects:
        raise RuntimeError("Resume extraction did not find any projects.")
