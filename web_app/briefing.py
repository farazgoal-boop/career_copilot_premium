"""Persistence and profile materialization for the Flask pre-interview briefing wizard."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

DEFAULT_BRIEFING_ID = "primary"


def load_briefing(storage_path: str | Path, briefing_id: str = DEFAULT_BRIEFING_ID) -> dict[str, Any]:
    path = Path(storage_path)
    if not path.exists():
        return _default_briefing_payload(briefing_id)

    payload = json.loads(path.read_text(encoding="utf-8"))
    briefings = payload.get("briefings", {}) if isinstance(payload, dict) else {}
    if not isinstance(briefings, dict):
        return _default_briefing_payload(briefing_id)
    saved = briefings.get(briefing_id)
    if not isinstance(saved, dict):
        return _default_briefing_payload(briefing_id)
    return {**_default_briefing_payload(briefing_id), **saved}


def save_briefing(storage_path: str | Path, briefing_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(storage_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    root: dict[str, Any] = {"briefings": {}}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("briefings"), dict):
            root = loaded

    briefing = {**_default_briefing_payload(briefing_id), **payload, "briefing_id": briefing_id}
    root["briefings"][briefing_id] = briefing
    path.write_text(json.dumps(root, indent=2), encoding="utf-8")
    return briefing


def materialize_briefing_profile(
    briefing: dict[str, Any],
    profiles_root: str | Path,
    *,
    session_mode: str = "progressive",
) -> tuple[Path, str, list[str]]:
    from desktop_app.onboarding import save_session_ready_profile, save_completed_profile, validate_profile  # noqa: PLC0415
    profile = build_profile_from_briefing(briefing)
    deferred_issues = validate_profile(profile)
    normalized_mode = str(session_mode or "progressive").strip().casefold()

    if not deferred_issues and normalized_mode != "resume_only":
        return save_completed_profile(profile, profiles_root), "complete", []

    return save_session_ready_profile(profile, profiles_root), "session_ready", deferred_issues


def build_operator_prompts(briefing: dict[str, Any]) -> dict[str, str]:
    answer_style = str(briefing.get("answer_style", "")).strip()
    strongest_skill = str(briefing.get("strongest_skill", "")).strip()
    target_role = str(briefing.get("target_role", "")).strip()
    company_name = str(briefing.get("company_name", "")).strip()
    meeting_source = str(briefing.get("meeting_source", "Manual / generic interview")).strip()
    company_values = str(briefing.get("company_values", "")).strip()
    live_constraints = str(briefing.get("live_constraints", "")).strip()
    expected_questions = _split_lines(briefing.get("expected_questions", ""))[:2]

    persistent_parts = [
        answer_style,
        f"Treat the live conversation as a {meeting_source} session." if meeting_source else "",
        f"Position answers for the {target_role} role." if target_role else "",
        f"Anchor examples around {strongest_skill}." if strongest_skill else "",
        f"Reflect {company_name} expectations and values." if company_name else "",
        company_values,
    ]
    live_parts = [
        live_constraints,
        f"Be ready for: {'; '.join(expected_questions)}." if expected_questions else "",
    ]

    return {
        "persistent_prompt": " ".join(part for part in persistent_parts if part).strip(),
        "live_prompt": " ".join(part for part in live_parts if part).strip(),
    }


def build_profile_from_briefing(briefing: dict[str, Any]):
    from desktop_app.onboarding import (  # noqa: PLC0415
        CompleteUserProfile, IdentitySetup, ProjectPortfolioEntry,
        ResumeConfirmation, SkillEntry, TargetJobProfile,
        WeaknessProfile, WorkHistoryEntry,
    )
    skills = _build_skill_entries(briefing)
    achievements = _split_lines(briefing.get("experience_highlights", ""))
    while len(achievements) < 3:
        achievements.append(
            [
                "Improved backend response times by 38%.",
                "Led a production release with zero rollback incidents.",
                "Improved collaboration through clearer technical communication.",
            ][len(achievements)]
        )

    project_description = str(briefing.get("project_summary", "")).strip() or (
        "Built an interview preparation workspace that combines live transcript awareness, prompt steering, and answer suggestions."
    )
    technical_weak_areas = _split_csv(briefing.get("technical_weak_areas", ""))[:4]
    if not technical_weak_areas:
        technical_weak_areas = ["System design", "Frontend architecture"]

    improvement_actions = _split_lines(briefing.get("improvement_actions", ""))[:4]
    if not improvement_actions:
        improvement_actions = [
            "Practice concise STAR answers",
            "Run mock interviews weekly",
        ]

    return CompleteUserProfile(
        identity=IdentitySetup(
            full_name=str(briefing.get("full_name", "Candidate")).strip() or "Candidate",
            current_role=str(briefing.get("current_role", "Professional")).strip() or "Professional",
            total_experience_years=float(briefing.get("experience_years", 0) or 0),
            location=str(briefing.get("location", "Remote")).strip() or "Remote",
            work_mode=_normalize_work_mode(briefing.get("work_mode", "Hybrid")),
        ),
        skills=skills,
        work_history=[
            WorkHistoryEntry(
                company_name=str(briefing.get("recent_company", "Recent Company")).strip() or "Recent Company",
                duration=str(briefing.get("work_duration", "Recent experience")).strip() or "Recent experience",
                achievements=achievements[:3],
                reason_for_leaving=str(briefing.get("reason_for_change", "Ready for the next role.")).strip() or "Ready for the next role.",
                salary_expectations=str(briefing.get("salary_expectations", "Open to market-competitive offers.")).strip() or "Open to market-competitive offers.",
            )
        ],
        projects=[
            ProjectPortfolioEntry(
                name=str(briefing.get("project_name", "Interview Preparation Workspace")).strip() or "Interview Preparation Workspace",
                description=project_description,
                technologies=_split_csv(briefing.get("project_technologies", "Python, Flask, SQLite"))[:5],
                contribution=str(briefing.get("project_contribution", "Designed the workflow, built the core experience, and connected AI answer generation.")).strip() or "Designed the workflow, built the core experience, and connected AI answer generation.",
                link=str(briefing.get("project_link", "")).strip() or None,
            )
        ],
        resume=ResumeConfirmation(
            filename=str(briefing.get("resume_filename", "resume.txt")).strip() or "resume.txt",
            extracted_text=str(briefing.get("resume_text", "Resume summary not provided.")).strip() or "Resume summary not provided.",
            confirmed=True,
            source_format="text",
        ),
        weaknesses=WeaknessProfile(
            english_fluency_level=int(briefing.get("english_fluency_level", 7) or 7),
            technical_weak_areas=technical_weak_areas,
            interview_anxiety_level=int(briefing.get("interview_anxiety_level", 4) or 4),
            previous_interview_failures=str(briefing.get("weakness_story", "Sometimes I rush answers under pressure.")).strip() or "Sometimes I rush answers under pressure.",
            improvement_actions=improvement_actions,
        ),
        target_job=TargetJobProfile(
            job_title=str(briefing.get("target_role", "Target Role")).strip() or "Target Role",
            industry=str(briefing.get("industry", "IT")).strip() or "IT",
            company_type=str(briefing.get("company_type", "Corporate")).strip() or "Corporate",
            interview_difficulty=_normalize_interview_difficulty(briefing.get("interview_difficulty", "Senior")),
        ),
    )


def _build_skill_entries(briefing: dict[str, Any]) -> list:
    from desktop_app.onboarding import SkillEntry  # noqa: PLC0415
    requested_skills = _split_csv(briefing.get("skills", ""))
    if briefing.get("strongest_skill"):
        requested_skills.insert(0, str(briefing["strongest_skill"]))

    defaults = [
        "Communication",
        "Problem Solving",
        "Leadership",
        "System Design",
        "APIs",
        "Testing",
        "SQL",
        "Python",
        "Stakeholder Management",
        "Mentoring",
    ]
    ordered: list[str] = []
    seen: set[str] = set()
    for item in requested_skills + defaults:
        cleaned = str(item).strip()
        if cleaned and cleaned.lower() not in seen:
            ordered.append(cleaned)
            seen.add(cleaned.lower())
    ordered = ordered[:10]

    entries: list[SkillEntry] = []
    strongest = str(briefing.get("strongest_skill", "")).strip().lower()
    for item in ordered:
        level = "Intermediate"
        if item.lower() == strongest:
            level = "Expert"
        elif item.lower() in {"python", "sql", "communication", "problem solving"}:
            level = "Expert"
        entries.append(SkillEntry(name=item, level=level))
    return entries


def _split_csv(value: object) -> list[str]:
    raw = str(value or "")
    return [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]


def _split_lines(value: object) -> list[str]:
    return [item.strip() for item in str(value or "").splitlines() if item.strip()]


def _normalize_work_mode(value: object) -> str:
    raw_value = str(value or "").strip()
    normalized = raw_value.casefold()
    if not normalized:
        return "Hybrid"
    if "remote" in normalized:
        return "Remote"
    if "hybrid" in normalized:
        return "Hybrid"
    if "office" in normalized or "on-site" in normalized or "onsite" in normalized:
        return "Office"
    return "Hybrid"


def _normalize_interview_difficulty(value: object) -> str:
    raw_value = str(value or "").strip()
    normalized = raw_value.casefold()
    if not normalized:
        return "Senior"
    if "junior" in normalized:
        return "Junior"
    if "mid" in normalized:
        return "Mid"
    if "lead" in normalized or "principal" in normalized or "architect" in normalized:
        return "Lead"
    if "senior" in normalized:
        return "Senior"
    return "Senior"


def _default_briefing_payload(briefing_id: str) -> dict[str, Any]:
    return {
        "briefing_id": briefing_id,
        "full_name": "",
        "current_role": "",
        "experience_years": 0,
        "location": "",
        "work_mode": "Hybrid",
        "resume_filename": "",
        "resume_text": "",
        "skills": "",
        "strongest_skill": "",
        "strongest_skill_example": "",
        "experience_highlights": "",
        "recent_company": "",
        "work_duration": "",
        "reason_for_change": "",
        "salary_expectations": "",
        "project_name": "",
        "project_summary": "",
        "project_technologies": "",
        "project_contribution": "",
        "project_link": "",
        "technical_weak_areas": "",
        "english_fluency_level": 7,
        "interview_anxiety_level": 4,
        "weakness_story": "",
        "improvement_actions": "",
        "target_role": "",
        "company_name": "",
        "meeting_source": "Manual / generic interview",
        "meeting_capture_mode": "Companion workspace with live mic capture",
        "meeting_window_name": "",
        "camera_layout_preference": "Keep Career Copilot beside the meeting window",
        "company_values": "",
        "industry": "IT",
        "company_type": "Corporate",
        "interview_difficulty": "Senior",
        "expected_questions": "",
        "answer_style": "Simple English, concise, confident-humble",
        "live_constraints": "Keep answers under 30 seconds where possible.",
        "profile_path": "",
    }