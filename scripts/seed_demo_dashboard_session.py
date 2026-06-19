from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop_app.audio_handler import AudioCapture
from desktop_app.onboarding import (
    CompleteUserProfile,
    IdentitySetup,
    ProjectPortfolioEntry,
    ResumeConfirmation,
    SkillEntry,
    TargetJobProfile,
    WeaknessProfile,
    WorkHistoryEntry,
    save_completed_profile,
)
from desktop_app.runtime_controller import build_session_runner


def build_demo_profile() -> CompleteUserProfile:
    return CompleteUserProfile(
        identity=IdentitySetup(
            full_name="Amina Khan",
            current_role="Senior Python Developer",
            total_experience_years=6,
            location="Lahore",
            work_mode="Hybrid",
        ),
        skills=[
            SkillEntry(name="Python", level="Expert"),
            SkillEntry(name="SQL", level="Expert"),
            SkillEntry(name="FastAPI", level="Intermediate"),
            SkillEntry(name="React", level="Intermediate"),
            SkillEntry(name="Docker", level="Intermediate"),
            SkillEntry(name="AWS", level="Intermediate"),
            SkillEntry(name="Leadership", level="Intermediate"),
            SkillEntry(name="Communication", level="Expert"),
            SkillEntry(name="Problem Solving", level="Expert"),
            SkillEntry(name="System Design", level="Intermediate"),
        ],
        work_history=[
            WorkHistoryEntry(
                company_name="Northstar Labs",
                duration="2021-2024",
                achievements=[
                    "Improved API response times by 38%.",
                    "Led migration of 12 services to containerized deployments.",
                    "Introduced test automation that reduced release regressions by 25%.",
                ],
                reason_for_leaving="Looking for a larger AI-focused engineering role.",
                salary_expectations="Market-competitive based on total package.",
            )
        ],
        projects=[
            ProjectPortfolioEntry(
                name="Interview Analytics Dashboard",
                description="Built a two-sided interview analytics dashboard that tracked candidate confidence and recruiter feedback across live sessions.",
                technologies=["Python", "FastAPI", "PostgreSQL"],
                contribution="Designed the data model, built the backend APIs, and implemented scoring logic.",
                link="https://github.com/example/interview-dashboard",
            )
        ],
        resume=ResumeConfirmation(
            filename="amina_khan_resume.pdf",
            extracted_text="Amina Khan is a Senior Python Developer with 6 years of experience.",
            confirmed=True,
            source_format="pdf",
        ),
        weaknesses=WeaknessProfile(
            english_fluency_level=7,
            technical_weak_areas=["Distributed tracing", "Advanced frontend architecture"],
            interview_anxiety_level=4,
            previous_interview_failures="I rushed answers in one system design interview and skipped measurable impact.",
            improvement_actions=["Practice concise STAR responses", "Record mock interviews twice a week"],
        ),
        target_job=TargetJobProfile(
            job_title="Staff Backend Engineer",
            industry="IT",
            company_type="Corporate",
            interview_difficulty="Senior",
        ),
    )


def main() -> int:
    project_root = PROJECT_ROOT
    profiles_root = project_root / "data" / "user_profiles"
    registry_path = project_root / "data" / "cache" / "session_registry.json"
    database_path = project_root / "data" / "cache" / "session_store.db"

    profile_path = save_completed_profile(build_demo_profile(), profiles_root)
    runner = build_session_runner(
        profile_directory=profile_path.parent,
        company_name="Acme AI",
        role_title="Staff Backend Engineer",
        session_registry_path=registry_path,
        session_database_path=database_path,
    )
    runner.start()
    runner.handle_auto_stop(
        AudioCapture(
            raw_audio=(10).to_bytes(2, byteorder="little", signed=True) * 20,
            started_at="2026-05-20T20:45:00+00:00",
            stopped_at="2026-05-20T20:45:03+00:00",
            duration_seconds=3.0,
            transcript_hint="Why should we hire you for this backend engineering role?",
            source="scripted",
        )
    )
    runner.stop()
    print(runner.session_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())