"""Phase 0 onboarding models, validation, and persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any

from .custom_dropdowns import load_dropdown_options

PROFILE_FILENAME = "user_complete_profile.json"
ONBOARDING_FLAG_FILENAME = "user_training_complete.flag"
SESSION_READY_FLAG_FILENAME = "user_session_ready.flag"
VALID_SKILL_LEVELS = {"beginner", "intermediate", "expert"}
VALID_WORK_MODES = {"remote", "office", "hybrid"}
VALID_INTERVIEW_DIFFICULTIES = {"junior", "mid", "senior", "lead"}


def _allowed_dropdown_values(field_key: str) -> set[str]:
    return {
        option.strip().casefold()
        for option in load_dropdown_options().get(field_key, [])
        if option.strip()
    }


@dataclass
class IdentitySetup:
    full_name: str
    current_role: str
    total_experience_years: float
    location: str
    work_mode: str


@dataclass
class SkillEntry:
    name: str
    level: str


@dataclass
class WorkHistoryEntry:
    company_name: str
    duration: str
    achievements: list[str]
    reason_for_leaving: str
    salary_expectations: str


@dataclass
class ProjectPortfolioEntry:
    name: str
    description: str
    technologies: list[str]
    contribution: str
    link: str | None = None


@dataclass
class ResumeConfirmation:
    filename: str
    extracted_text: str
    confirmed: bool
    source_format: str = "unknown"


@dataclass
class WeaknessProfile:
    english_fluency_level: int
    technical_weak_areas: list[str]
    interview_anxiety_level: int
    previous_interview_failures: str
    improvement_actions: list[str] = field(default_factory=list)


@dataclass
class TargetJobProfile:
    job_title: str
    industry: str
    company_type: str
    interview_difficulty: str


@dataclass
class CompleteUserProfile:
    identity: IdentitySetup
    skills: list[SkillEntry]
    work_history: list[WorkHistoryEntry]
    projects: list[ProjectPortfolioEntry]
    resume: ResumeConfirmation
    weaknesses: WeaknessProfile
    target_job: TargetJobProfile
    profile_version: str = "1.0"
    created_at: str = field(default_factory=lambda: _utc_now_iso())
    updated_at: str = field(default_factory=lambda: _utc_now_iso())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_profile_storage_path(base_directory: str | Path, full_name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", full_name.strip().lower()).strip("-")
    if not slug:
        slug = "candidate"
    return Path(base_directory) / slug


def validate_profile(profile: CompleteUserProfile) -> list[str]:
    issues: list[str] = []

    if not profile.identity.full_name.strip():
        issues.append("Identity setup requires the full name from the resume.")
    if not profile.identity.current_role.strip():
        issues.append("Identity setup requires the current role or job title.")
    if profile.identity.total_experience_years < 0:
        issues.append("Total experience cannot be negative.")
    if not profile.identity.location.strip():
        issues.append("Identity setup requires a location.")
    if profile.identity.work_mode.strip().casefold() not in _allowed_dropdown_values("work_modes"):
        issues.append("Work mode must be Remote, Office, or Hybrid.")

    if len(profile.skills) < 10:
        issues.append("Skills inventory must contain at least 10 skills.")
    for skill in profile.skills:
        if not skill.name.strip():
            issues.append("Every skill entry must include a skill name.")
        if skill.level.strip().casefold() not in _allowed_dropdown_values("skill_levels"):
            issues.append(f"Skill level for '{skill.name or 'unknown'}' must be Beginner, Intermediate, or Expert.")

    if not profile.work_history:
        issues.append("Work history must include at least one job entry.")
    for entry in profile.work_history:
        if not entry.company_name.strip():
            issues.append("Each work history entry needs a company name.")
        if not entry.duration.strip():
            issues.append(f"Work history for '{entry.company_name or 'unknown'}' needs a duration.")
        if len([item for item in entry.achievements if item.strip()]) < 3:
            issues.append(f"Work history for '{entry.company_name or 'unknown'}' must include at least 3 achievements.")
        if not entry.reason_for_leaving.strip():
            issues.append(f"Work history for '{entry.company_name or 'unknown'}' requires a reason for leaving.")
        if not entry.salary_expectations.strip():
            issues.append(f"Work history for '{entry.company_name or 'unknown'}' requires salary expectations.")

    if not profile.projects:
        issues.append("Project portfolio must include at least one project.")
    for project in profile.projects:
        if not project.name.strip():
            issues.append("Each project needs a project name.")
        if len(project.description.strip()) < 20:
            issues.append(f"Project '{project.name or 'unknown'}' needs a meaningful two-line style description.")
        if not project.technologies:
            issues.append(f"Project '{project.name or 'unknown'}' must include technologies used.")
        if not project.contribution.strip():
            issues.append(f"Project '{project.name or 'unknown'}' must include the user's contribution.")

    if not profile.resume.filename.strip():
        issues.append("Resume upload requires a filename.")
    if not profile.resume.extracted_text.strip():
        issues.append("Resume upload requires extracted resume text.")
    if not profile.resume.confirmed:
        issues.append("Resume extraction must be confirmed by the user before interview mode is enabled.")

    if not 1 <= profile.weaknesses.english_fluency_level <= 10:
        issues.append("English fluency level must be between 1 and 10.")
    if not profile.weaknesses.technical_weak_areas:
        issues.append("Weakness profile must include technical weak areas.")
    if not 1 <= profile.weaknesses.interview_anxiety_level <= 10:
        issues.append("Interview anxiety level must be between 1 and 10.")
    if not profile.weaknesses.previous_interview_failures.strip():
        issues.append("Weakness profile must describe previous interview failures.")

    if not profile.target_job.job_title.strip():
        issues.append("Target job profile requires a job title.")
    if not profile.target_job.industry.strip():
        issues.append("Target job profile requires an industry.")
    if not profile.target_job.company_type.strip():
        issues.append("Target job profile requires a company type.")
    if profile.target_job.interview_difficulty.strip().casefold() not in _allowed_dropdown_values("difficulty_levels"):
        issues.append("Interview difficulty must be Junior, Mid, Senior, or Lead.")

    return issues


def validate_session_ready_profile(profile: CompleteUserProfile) -> list[str]:
    issues: list[str] = []

    if not profile.resume.filename.strip():
        issues.append("Resume upload requires a filename.")
    if not profile.resume.extracted_text.strip():
        issues.append("Resume upload requires extracted resume text.")
    if not profile.resume.confirmed:
        issues.append("Resume extraction must be confirmed before instant session mode is enabled.")
    if not profile.identity.full_name.strip():
        issues.append("Resume-only mode still needs a candidate name or a generated fallback.")
    if not profile.target_job.job_title.strip():
        issues.append("Resume-only mode still needs a target role or a generated fallback.")

    return issues


def save_completed_profile(profile: CompleteUserProfile, base_directory: str | Path) -> Path:
    issues = validate_profile(profile)
    if issues:
        raise ValueError("Cannot persist incomplete onboarding profile: " + "; ".join(issues))

    return _persist_profile(profile, base_directory, is_complete=True)


def save_session_ready_profile(profile: CompleteUserProfile, base_directory: str | Path) -> Path:
    issues = validate_session_ready_profile(profile)
    if issues:
        raise ValueError("Cannot persist session-ready profile: " + "; ".join(issues))

    return _persist_profile(profile, base_directory, is_complete=False)


def _persist_profile(profile: CompleteUserProfile, base_directory: str | Path, *, is_complete: bool) -> Path:
    profile.updated_at = _utc_now_iso()
    profile_directory = build_profile_storage_path(base_directory, profile.identity.full_name)
    profile_directory.mkdir(parents=True, exist_ok=True)

    profile_path = profile_directory / PROFILE_FILENAME
    profile_path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")

    flag_path = profile_directory / ONBOARDING_FLAG_FILENAME
    if is_complete:
        flag_path.write_text("complete\n", encoding="utf-8")
    elif flag_path.exists():
        flag_path.unlink()

    session_ready_flag_path = profile_directory / SESSION_READY_FLAG_FILENAME
    session_ready_flag_path.write_text(("complete" if is_complete else "session-ready") + "\n", encoding="utf-8")

    return profile_path


def load_completed_profile(profile_path: str | Path) -> CompleteUserProfile:
    payload = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    return CompleteUserProfile(
        identity=IdentitySetup(**payload["identity"]),
        skills=[SkillEntry(**skill) for skill in payload["skills"]],
        work_history=[WorkHistoryEntry(**entry) for entry in payload["work_history"]],
        projects=[ProjectPortfolioEntry(**project) for project in payload["projects"]],
        resume=ResumeConfirmation(**payload["resume"]),
        weaknesses=WeaknessProfile(**payload["weaknesses"]),
        target_job=TargetJobProfile(**payload["target_job"]),
        profile_version=payload.get("profile_version", "1.0"),
        created_at=payload.get("created_at", _utc_now_iso()),
        updated_at=payload.get("updated_at", _utc_now_iso()),
    )


def is_training_complete(profile_directory: str | Path) -> bool:
    directory = Path(profile_directory)
    return (directory / PROFILE_FILENAME).exists() and (directory / ONBOARDING_FLAG_FILENAME).exists()


def is_session_ready(profile_directory: str | Path) -> bool:
    directory = Path(profile_directory)
    profile_exists = (directory / PROFILE_FILENAME).exists()
    return profile_exists and (
        (directory / ONBOARDING_FLAG_FILENAME).exists()
        or (directory / SESSION_READY_FLAG_FILENAME).exists()
    )
