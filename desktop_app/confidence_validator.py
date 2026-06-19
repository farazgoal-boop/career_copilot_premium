"""Confidence scoring for pre-interview readiness."""

from __future__ import annotations

from dataclasses import dataclass

from .onboarding import CompleteUserProfile


@dataclass
class ConfidenceAssessment:
    score: int
    band: str
    action_plan: str


def assess_interview_confidence(profile: CompleteUserProfile, role_title: str) -> ConfidenceAssessment:
    score = 40
    score += min(len(profile.skills), 12) * 2
    score += min(len(profile.projects), 3) * 4
    score += min(len(profile.work_history), 3) * 5
    score += max(0, 10 - profile.weaknesses.interview_anxiety_level) * 2
    score += max(0, profile.weaknesses.english_fluency_level - 5) * 2

    if any(role_title.lower() in role.lower() for role in [profile.identity.current_role, profile.target_job.job_title]):
        score += 6

    score = max(0, min(score, 95))

    if score < 60:
        weak_areas = ", ".join(profile.weaknesses.technical_weak_areas[:2])
        return ConfidenceAssessment(
            score=score,
            band="below_60",
            action_plan=f"You need 2 days of practice on {weak_areas}.",
        )

    if score <= 80:
        weak_area = profile.weaknesses.technical_weak_areas[0]
        return ConfidenceAssessment(
            score=score,
            band="60_to_80",
            action_plan=f"You are ready but prepare {weak_area} with sharper examples.",
        )

    improvement = profile.weaknesses.technical_weak_areas[0]
    return ConfidenceAssessment(
        score=score,
        band="above_80",
        action_plan=f"You are ready. Focus on one improvement: {improvement}.",
    )