"""Phase 1 strategy generation based on a completed user profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .confidence_validator import ConfidenceAssessment, assess_interview_confidence
from .fallback_manager import build_fallback_plan
from .onboarding import CompleteUserProfile


@dataclass
class CompanyResearchBrief:
    company_name: str
    role_title: str
    common_questions: list[str]
    company_values: list[str]
    red_flags: list[str]


@dataclass
class PersonalizedAnswerTemplates:
    tell_me_about_yourself: str
    why_should_we_hire_you: str
    what_is_your_weakness: str


@dataclass
class ExpectedQuestion:
    question: str
    suggested_answer: str
    keywords_to_listen_for: list[str]
    difficulty: str


@dataclass
class StrategyPack:
    company_brief: CompanyResearchBrief
    answer_templates: PersonalizedAnswerTemplates
    expected_questions: list[ExpectedQuestion]
    fallback_plan: dict[str, str]
    confidence: ConfidenceAssessment

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_strategy_pack(
    profile: CompleteUserProfile,
    company_name: str,
    role_title: str,
    company_values: list[str] | None = None,
) -> StrategyPack:
    normalized_values = company_values or _default_company_values(company_name)
    top_skills = [skill.name for skill in profile.skills[:3]]
    latest_job = profile.work_history[0]
    latest_project = profile.projects[0]
    weakest_area = profile.weaknesses.technical_weak_areas[0]

    answer_templates = PersonalizedAnswerTemplates(
        tell_me_about_yourself=(
            f"Hi, I'm {profile.identity.full_name}. I have {profile.identity.total_experience_years} years of "
            f"{top_skills[0]} and {top_skills[1]} experience. Most recently at {latest_job.company_name}, "
            f"I worked on {latest_project.name} where I {latest_job.achievements[0].rstrip('.')}"
        ),
        why_should_we_hire_you=(
            f"My strongest skill is {top_skills[0]}. For example, at {latest_job.company_name}, I "
            f"{latest_job.achievements[0].rstrip('.')}. I also understand {top_skills[1]}, which this {role_title} role needs."
        ),
        what_is_your_weakness=(
            f"Honestly, {weakest_area} has been a growth area for me, but I'm actively improving by "
            f"{profile.weaknesses.improvement_actions[0].lower()}. For example, recently I {latest_job.achievements[1].rstrip('.').lower()}."
        ),
    )

    expected_questions = _build_expected_questions(profile, company_name, role_title)
    company_brief = CompanyResearchBrief(
        company_name=company_name,
        role_title=role_title,
        common_questions=[item.question for item in expected_questions[:5]],
        company_values=normalized_values,
        red_flags=[
            f"If {company_name} cannot define success metrics for the {role_title} role.",
            "If interviewers dismiss collaboration, feedback, or ownership questions.",
            "If the role expects senior impact without matching scope or support.",
        ],
    )

    return StrategyPack(
        company_brief=company_brief,
        answer_templates=answer_templates,
        expected_questions=expected_questions,
        fallback_plan=build_fallback_plan(),
        confidence=assess_interview_confidence(profile, role_title),
    )


def save_strategy_pack(strategy_pack: StrategyPack, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(strategy_pack.to_dict(), indent=2), encoding="utf-8")
    return path


def load_strategy_pack(source: str | Path) -> StrategyPack:
    path = Path(source)
    payload = json.loads(path.read_text(encoding="utf-8"))
    company_brief = CompanyResearchBrief(**payload["company_brief"])
    answer_templates = PersonalizedAnswerTemplates(**payload["answer_templates"])
    expected_questions = [ExpectedQuestion(**item) for item in payload.get("expected_questions", [])]
    confidence_payload = payload.get("confidence", {})
    confidence = ConfidenceAssessment(
        score=int(confidence_payload.get("score", 70) or 70),
        band=str(confidence_payload.get("band", "Ready") or "Ready"),
        action_plan=str(confidence_payload.get("action_plan", "") or ""),
    )
    return StrategyPack(
        company_brief=company_brief,
        answer_templates=answer_templates,
        expected_questions=expected_questions,
        fallback_plan=dict(payload.get("fallback_plan", {})),
        confidence=confidence,
    )


def _build_expected_questions(
    profile: CompleteUserProfile,
    company_name: str,
    role_title: str,
) -> list[ExpectedQuestion]:
    latest_job = profile.work_history[0]
    latest_project = profile.projects[0]
    top_skills = [skill.name for skill in profile.skills[:3]]
    weak_areas = profile.weaknesses.technical_weak_areas
    question_specs = [
        (f"Tell me about yourself for this {role_title} role.", "Easy", [role_title, top_skills[0], latest_job.company_name]),
        (f"Why do you want to join {company_name}?", "Easy", [company_name, "motivation", "values"]),
        (f"Why should we hire you as a {role_title}?", "Easy", [top_skills[0], top_skills[1], "impact"]),
        (f"Describe a project where you used {top_skills[0]}.", "Easy", [top_skills[0], latest_project.name, "results"]),
        (f"Tell me about a time you solved a difficult problem at {latest_job.company_name}.", "Medium", ["problem solving", latest_job.company_name, "tradeoff"]),
        (f"How do you handle collaboration and leadership in engineering teams?", "Medium", ["leadership", "communication", "ownership"]),
        (f"What is your biggest weakness right now?", "Medium", [weak_areas[0], "improvement", "learning"]),
        (f"How would you approach a challenging {top_skills[1]} requirement in this role?", "Medium", [top_skills[1], role_title, "approach"]),
        (f"What did you learn from your previous interview setbacks?", "Medium", ["reflection", "improvement", "practice"]),
        (f"How do you prioritize tasks in a fast-moving company?", "Medium", ["prioritization", "execution", "stakeholders"]),
        (f"Explain a production issue you handled and what changed afterward.", "Tricky", ["incident", "root cause", "prevention"]),
        (f"How do you measure success for a {role_title}?", "Tricky", ["metrics", "impact", "ownership"]),
        (f"What would your first 90 days at {company_name} look like?", "Tricky", ["90 days", company_name, "plan"]),
        (f"How would you mentor junior teammates while delivering senior-level work?", "Tricky", ["mentoring", "delivery", "quality"]),
        (f"What makes you a better fit than other candidates for this role?", "Tricky", [top_skills[0], top_skills[2], "differentiator"]),
    ]

    questions: list[ExpectedQuestion] = []
    for prompt, difficulty, keywords in question_specs:
        answer = _build_answer(prompt, profile, role_title, latest_job.company_name, latest_project.name)
        questions.append(
            ExpectedQuestion(
                question=prompt,
                suggested_answer=answer,
                keywords_to_listen_for=keywords,
                difficulty=difficulty,
            )
        )
    return questions


def _build_answer(
    question: str,
    profile: CompleteUserProfile,
    role_title: str,
    latest_company: str,
    latest_project: str,
) -> str:
    strongest_skill = profile.skills[0].name
    second_skill = profile.skills[1].name
    achievement = profile.work_history[0].achievements[0].rstrip(".")
    return (
        f"For {question.lower()} I would anchor my answer in my {profile.identity.total_experience_years} years of experience, "
        f"especially using {strongest_skill} and {second_skill}. At {latest_company}, I {achievement}. "
        f"That gives me a practical example I can connect to {role_title} responsibilities and the work I delivered on {latest_project}."
    )


def _default_company_values(company_name: str) -> list[str]:
    return [
        f"Strong ownership mindset aligned with {company_name}'s growth stage",
        "Clear communication and cross-functional collaboration",
        "Measured execution with visible customer or business impact",
    ]