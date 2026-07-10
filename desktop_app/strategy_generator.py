"""Phase 1 strategy generation based on a completed user profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from .confidence_validator import ConfidenceAssessment, assess_interview_confidence
from .fallback_manager import build_fallback_plan
from .onboarding import CompleteUserProfile
from .session_types import DEFAULT_SESSION_TYPE, normalize_session_type


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
class ResumeHighlight:
    text: str
    keywords: list[str]


@dataclass
class StrategyPack:
    company_brief: CompanyResearchBrief
    answer_templates: PersonalizedAnswerTemplates
    expected_questions: list[ExpectedQuestion]
    fallback_plan: dict[str, str]
    confidence: ConfidenceAssessment
    resume_highlights: list[ResumeHighlight]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_strategy_pack(
    profile: CompleteUserProfile,
    company_name: str,
    role_title: str,
    company_values: list[str] | None = None,
    session_type: str = DEFAULT_SESSION_TYPE,
) -> StrategyPack:
    """Build a strategy pack whose questions, templates, and framing match session_type.

    answer_templates keeps the same 3 field names (tell_me_about_yourself,
    why_should_we_hire_you, what_is_your_weakness) across every type -- they're
    treated as generic slots (opening pitch / strongest value point / honest
    caveat) rather than literal interview questions, so answer_builder.py's
    existing references to them work unchanged for every session_type.
    """
    normalized_type = normalize_session_type(session_type)
    normalized_values = company_values or _default_company_values(company_name)
    top_skills = [skill.name for skill in profile.skills[:3]]
    latest_job = profile.work_history[0]
    latest_project = profile.projects[0]
    weakest_area = profile.weaknesses.technical_weak_areas[0]

    answer_templates = _build_answer_templates(
        normalized_type, profile, company_name, role_title, top_skills, latest_job, latest_project, weakest_area
    )
    expected_questions = _build_expected_questions(normalized_type, profile, company_name, role_title)
    company_brief = CompanyResearchBrief(
        company_name=company_name,
        role_title=role_title,
        common_questions=[item.question for item in expected_questions[:5]],
        company_values=normalized_values,
        red_flags=_build_red_flags(normalized_type, company_name, role_title),
    )

    return StrategyPack(
        company_brief=company_brief,
        answer_templates=answer_templates,
        expected_questions=expected_questions,
        fallback_plan=build_fallback_plan(),
        confidence=assess_interview_confidence(profile, role_title),
        resume_highlights=build_resume_highlights(profile),
    )


def build_resume_highlights(profile: CompleteUserProfile) -> list[ResumeHighlight]:
    """Flatten the full resume (every skill/achievement/project, not just the top-3/latest
    used for templates above) into keyword-tagged highlights so a live question can be
    matched against the most relevant specific experience, not always the same one.
    """
    highlights: list[ResumeHighlight] = []
    for skill in profile.skills:
        highlights.append(
            ResumeHighlight(
                text=f"Skilled in {skill.name} ({skill.level} level).",
                keywords=_tokenize(skill.name),
            )
        )
    for job in profile.work_history:
        for achievement in job.achievements:
            if not achievement.strip():
                continue
            highlights.append(
                ResumeHighlight(
                    text=f"At {job.company_name}: {achievement}",
                    keywords=list(set(_tokenize(achievement)) | set(_tokenize(job.company_name))),
                )
            )
    for project in profile.projects:
        detail = project.description.strip() or project.contribution.strip()
        highlights.append(
            ResumeHighlight(
                text=f"On {project.name}: {detail}" if detail else f"Worked on {project.name}.",
                keywords=list(
                    set(_tokenize(project.name))
                    | set(_tokenize(detail))
                    | {tech.strip().lower() for tech in project.technologies if tech.strip()}
                ),
            )
        )
    return highlights


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


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
    resume_highlights = [ResumeHighlight(**item) for item in payload.get("resume_highlights", [])]
    return StrategyPack(
        company_brief=company_brief,
        answer_templates=answer_templates,
        expected_questions=expected_questions,
        fallback_plan=dict(payload.get("fallback_plan", {})),
        confidence=confidence,
        resume_highlights=resume_highlights,
    )


# ---------------------------------------------------------------------------
# Answer templates (tell_me_about_yourself / why_should_we_hire_you / what_is_your_weakness)
# ---------------------------------------------------------------------------

def _build_answer_templates(
    session_type: str,
    profile: CompleteUserProfile,
    company_name: str,
    role_title: str,
    top_skills: list[str],
    latest_job,
    latest_project,
    weakest_area: str,
) -> PersonalizedAnswerTemplates:
    builders = {
        "job_interview": _job_interview_templates,
        "client_presentation": _client_presentation_templates,
        "product_demo": _product_demo_templates,
        "team_meeting": _team_meeting_templates,
        "sales_call": _sales_call_templates,
    }
    builder = builders.get(session_type, _job_interview_templates)
    return builder(profile, company_name, role_title, top_skills, latest_job, latest_project, weakest_area)


def _job_interview_templates(profile, company_name, role_title, top_skills, latest_job, latest_project, weakest_area) -> PersonalizedAnswerTemplates:
    return PersonalizedAnswerTemplates(
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


def _client_presentation_templates(profile, company_name, role_title, top_skills, latest_job, latest_project, weakest_area) -> PersonalizedAnswerTemplates:
    return PersonalizedAnswerTemplates(
        tell_me_about_yourself=(
            f"I'm {profile.identity.full_name}, and I'll be leading the {role_title} side of this engagement with {company_name}. "
            f"I bring {profile.identity.total_experience_years} years focused on {top_skills[0]}, most recently delivering "
            f"{latest_project.name}, where {latest_job.achievements[0].rstrip('.').lower()}."
        ),
        why_should_we_hire_you=(
            f"The strongest reason to move forward with us is {top_skills[0]}: on {latest_project.name} "
            f"{latest_job.achievements[0].rstrip('.').lower()}, and we'd apply the same rigor to {company_name}'s goals."
        ),
        what_is_your_weakness=(
            f"To be transparent, {weakest_area} is an area we manage carefully rather than overpromise on, "
            f"so we plan for it early by {profile.weaknesses.improvement_actions[0].lower()}."
        ),
    )


def _product_demo_templates(profile, company_name, role_title, top_skills, latest_job, latest_project, weakest_area) -> PersonalizedAnswerTemplates:
    return PersonalizedAnswerTemplates(
        tell_me_about_yourself=(
            f"I'm {profile.identity.full_name}, {role_title}, and I'll be walking you through the product today. "
            f"My background is in {top_skills[0]}, and I built {latest_project.name}, which is close to what we're about to see."
        ),
        why_should_we_hire_you=(
            f"The key differentiator here is {top_skills[0]}: it's the same strength behind {latest_project.name}, where "
            f"{latest_job.achievements[0].rstrip('.').lower()} -- that's the outcome this product is built to repeat for {company_name}."
        ),
        what_is_your_weakness=(
            f"One honest limitation right now is {weakest_area}; it's on our roadmap and we're addressing it by "
            f"{profile.weaknesses.improvement_actions[0].lower()}, so it's fair to raise before you commit."
        ),
    )


def _team_meeting_templates(profile, company_name, role_title, top_skills, latest_job, latest_project, weakest_area) -> PersonalizedAnswerTemplates:
    return PersonalizedAnswerTemplates(
        tell_me_about_yourself=(
            f"Quick context: I'm {profile.identity.full_name}, working as {role_title} on {latest_project.name}. "
            f"Current status -- {latest_job.achievements[0].rstrip('.').lower()}."
        ),
        why_should_we_hire_you=(
            f"My recommendation is to keep leaning on {top_skills[0]} here: it's what let us achieve "
            f"{latest_job.achievements[0].rstrip('.').lower()}, and the same approach applies to what {company_name} needs next."
        ),
        what_is_your_weakness=(
            f"The risk I want to flag is {weakest_area} -- I'm addressing it by "
            f"{profile.weaknesses.improvement_actions[0].lower()}, but the team should know it's not fully resolved yet."
        ),
    )


def _sales_call_templates(profile, company_name, role_title, top_skills, latest_job, latest_project, weakest_area) -> PersonalizedAnswerTemplates:
    return PersonalizedAnswerTemplates(
        tell_me_about_yourself=(
            f"I'm {profile.identity.full_name}, {role_title}. We help teams like {company_name} with exactly the kind of "
            f"work behind {latest_project.name}, where {latest_job.achievements[0].rstrip('.').lower()}."
        ),
        why_should_we_hire_you=(
            f"The reason to go with us is {top_skills[0]}: on {latest_project.name} "
            f"{latest_job.achievements[0].rstrip('.').lower()}, and that's the exact outcome {company_name} is asking for."
        ),
        what_is_your_weakness=(
            f"I'll be upfront that {weakest_area} is a fair objection -- we handle it by "
            f"{profile.weaknesses.improvement_actions[0].lower()}, and I'd rather tell you now than have it surprise you later."
        ),
    )


# ---------------------------------------------------------------------------
# Expected questions
# ---------------------------------------------------------------------------

def _build_expected_questions(
    session_type: str,
    profile: CompleteUserProfile,
    company_name: str,
    role_title: str,
) -> list[ExpectedQuestion]:
    builders = {
        "job_interview": _job_interview_questions,
        "client_presentation": _client_presentation_questions,
        "product_demo": _product_demo_questions,
        "team_meeting": _team_meeting_questions,
        "sales_call": _sales_call_questions,
    }
    builder = builders.get(session_type, _job_interview_questions)
    return builder(profile, company_name, role_title)


def _job_interview_questions(profile: CompleteUserProfile, company_name: str, role_title: str) -> list[ExpectedQuestion]:
    latest_job = profile.work_history[0]
    latest_project = profile.projects[0]
    top_skills = [skill.name for skill in profile.skills[:3]]
    weak_areas = profile.weaknesses.technical_weak_areas
    specs = [
        (f"Tell me about yourself for this {role_title} role.", "Easy", [role_title, top_skills[0], latest_job.company_name]),
        (f"Why do you want to join {company_name}?", "Easy", [company_name, "motivation", "values"]),
        (f"Why should we hire you as a {role_title}?", "Easy", [top_skills[0], top_skills[1], "impact"]),
        (f"Describe a project where you used {top_skills[0]}.", "Easy", [top_skills[0], latest_project.name, "results"]),
        (f"Tell me about a time you solved a difficult problem at {latest_job.company_name}.", "Medium", ["problem solving", latest_job.company_name, "tradeoff"]),
        ("How do you handle collaboration and leadership in engineering teams?", "Medium", ["leadership", "communication", "ownership"]),
        ("What is your biggest weakness right now?", "Medium", [weak_areas[0], "improvement", "learning"]),
        (f"How would you approach a challenging {top_skills[1]} requirement in this role?", "Medium", [top_skills[1], role_title, "approach"]),
        ("What did you learn from your previous interview setbacks?", "Medium", ["reflection", "improvement", "practice"]),
        ("How do you prioritize tasks in a fast-moving company?", "Medium", ["prioritization", "execution", "stakeholders"]),
        ("Explain a production issue you handled and what changed afterward.", "Tricky", ["incident", "root cause", "prevention"]),
        (f"How do you measure success for a {role_title}?", "Tricky", ["metrics", "impact", "ownership"]),
        (f"What would your first 90 days at {company_name} look like?", "Tricky", ["90 days", company_name, "plan"]),
        ("How would you mentor junior teammates while delivering senior-level work?", "Tricky", ["mentoring", "delivery", "quality"]),
        ("What makes you a better fit than other candidates for this role?", "Tricky", [top_skills[0], top_skills[2], "differentiator"]),
    ]
    return _finalize_questions(specs, profile, company_name, role_title, _job_interview_answer)


def _client_presentation_questions(profile: CompleteUserProfile, company_name: str, role_title: str) -> list[ExpectedQuestion]:
    specs = [
        (f"Can you walk us through your proposed solution for {company_name}?", "Easy", [company_name, "solution", "overview"]),
        ("Why did you choose this approach over alternatives?", "Easy", ["approach", "rationale", "tradeoff"]),
        ("What's your timeline for delivery?", "Easy", ["timeline", "delivery", "milestones"]),
        (f"How does this align with {company_name}'s budget?", "Easy", ["budget", "cost", "value"]),
        ("What risks do you see in this project?", "Medium", ["risk", "mitigation", "contingency"]),
        ("How will you measure success?", "Medium", ["metrics", "success", "outcome"]),
        ("What happens if requirements change mid-project?", "Medium", ["scope", "change", "flexibility"]),
        ("Can you share examples of similar work you've delivered?", "Medium", ["case study", "experience", "proof"]),
        ("Who will be our main point of contact?", "Medium", ["contact", "communication", "ownership"]),
        ("What support do you provide after delivery?", "Medium", ["support", "maintenance", "handover"]),
        ("How do you handle scope creep?", "Tricky", ["scope creep", "boundaries", "change control"]),
        ("What makes your proposal different from competitors?", "Tricky", ["differentiator", "value", "competitors"]),
        ("What's included versus what would be an additional cost?", "Tricky", ["scope", "cost", "inclusions"]),
        ("How do you ensure quality throughout the project?", "Tricky", ["quality", "process", "review"]),
        (f"What do you need from {company_name} to get started?", "Tricky", ["dependencies", "kickoff", "requirements"]),
    ]
    return _finalize_questions(specs, profile, company_name, role_title, _client_presentation_answer)


def _product_demo_questions(profile: CompleteUserProfile, company_name: str, role_title: str) -> list[ExpectedQuestion]:
    specs = [
        ("Can you show us how this feature works?", "Easy", ["feature", "walkthrough", "demo"]),
        (f"How does this integrate with {company_name}'s existing tools?", "Easy", ["integration", "compatibility", "workflow"]),
        ("What's the pricing model?", "Easy", ["pricing", "cost", "plans"]),
        ("How long does onboarding typically take?", "Easy", ["onboarding", "timeline", "setup"]),
        (f"Is this customizable for {company_name}'s specific use case?", "Medium", ["customization", "use case", "flexibility"]),
        ("What kind of support is included?", "Medium", ["support", "SLA", "helpdesk"]),
        ("How do you handle data security and privacy?", "Medium", ["security", "privacy", "compliance"]),
        ("Can we see this working with our own data?", "Medium", ["pilot", "sandbox", "trial"]),
        ("What's on your product roadmap?", "Medium", ["roadmap", "future", "upcoming features"]),
        ("How does this compare to what we're using now?", "Medium", ["comparison", "differentiator", "migration"]),
        ("What happens if we outgrow the current plan?", "Tricky", ["scalability", "upgrade", "plan"]),
        ("Who else is using this successfully?", "Tricky", ["references", "case study", "adoption"]),
        (f"What's the learning curve for {company_name}'s team?", "Tricky", ["learning curve", "training", "adoption"]),
        ("Can you walk through a use case relevant to our situation?", "Tricky", ["use case", "relevance", "example"]),
        ("What are the next steps if we want to move forward?", "Tricky", ["next steps", "onboarding", "decision"]),
    ]
    return _finalize_questions(specs, profile, company_name, role_title, _product_demo_answer)


def _team_meeting_questions(profile: CompleteUserProfile, company_name: str, role_title: str) -> list[ExpectedQuestion]:
    specs = [
        ("What's the status on your current tasks?", "Easy", ["status", "update", "progress"]),
        ("Are there any blockers we should know about?", "Easy", ["blocker", "risk", "dependency"]),
        ("What's your plan for this week?", "Easy", ["plan", "priorities", "next steps"]),
        ("How confident are you in hitting the deadline?", "Easy", ["deadline", "confidence", "timeline"]),
        ("Do you need help from anyone on the team?", "Medium", ["support", "collaboration", "help"]),
        ("What did you learn from the last sprint or cycle?", "Medium", ["retrospective", "learning", "improvement"]),
        ("Can you walk us through your approach to this problem?", "Medium", ["approach", "reasoning", "method"]),
        ("What tradeoffs did you consider?", "Medium", ["tradeoff", "decision", "alternatives"]),
        ("How does this affect other teams' work?", "Medium", ["dependency", "impact", "coordination"]),
        ("What's the biggest risk right now?", "Medium", ["risk", "mitigation", "priority"]),
        (f"Can you summarize the key decision {company_name} needs to make today?", "Tricky", ["decision", "summary", "recommendation"]),
        ("What feedback do you have on the current process?", "Tricky", ["feedback", "process", "improvement"]),
        ("How should we prioritize this against other work?", "Tricky", ["prioritization", "tradeoff", "impact"]),
        ("What support do you need from leadership?", "Tricky", ["escalation", "support", "resources"]),
        ("What's the next milestone we're tracking toward?", "Tricky", ["milestone", "plan", "timeline"]),
    ]
    return _finalize_questions(specs, profile, company_name, role_title, _team_meeting_answer)


def _sales_call_questions(profile: CompleteUserProfile, company_name: str, role_title: str) -> list[ExpectedQuestion]:
    specs = [
        ("What exactly does your product do?", "Easy", ["overview", "product", "value"]),
        (f"How is this different from what {company_name} is using now?", "Easy", ["differentiator", "comparison", "migration"]),
        ("What does pricing look like?", "Easy", ["pricing", "cost", "plans"]),
        ("How long does implementation take?", "Easy", ["implementation", "timeline", "onboarding"]),
        ("What kind of ROI can we expect?", "Medium", ["ROI", "value", "outcome"]),
        ("Can you share case studies or references?", "Medium", ["case study", "reference", "proof"]),
        ("What if it doesn't work for our team?", "Medium", ["risk", "guarantee", "objection"]),
        ("Is there a contract commitment?", "Medium", ["contract", "commitment", "terms"]),
        ("What support do you offer during onboarding?", "Medium", ["support", "onboarding", "success"]),
        ("How do you handle data security?", "Medium", ["security", "compliance", "privacy"]),
        (f"Why should {company_name} choose you over the competition?", "Tricky", ["differentiator", "competitors", "value"]),
        ("What happens after the trial period?", "Tricky", ["trial", "conversion", "next steps"]),
        ("Who else on our team should be involved in this decision?", "Tricky", ["stakeholders", "decision", "process"]),
        ("What's the biggest risk in switching to your solution?", "Tricky", ["risk", "objection", "migration"]),
        ("What would the next steps look like if we move forward?", "Tricky", ["next steps", "close", "onboarding"]),
    ]
    return _finalize_questions(specs, profile, company_name, role_title, _sales_call_answer)


def _finalize_questions(
    specs: list[tuple[str, str, list[str]]],
    profile: CompleteUserProfile,
    company_name: str,
    role_title: str,
    answer_builder,
) -> list[ExpectedQuestion]:
    latest_job = profile.work_history[0]
    latest_project = profile.projects[0]
    questions: list[ExpectedQuestion] = []
    for prompt, difficulty, keywords in specs:
        answer = answer_builder(prompt, profile, company_name, role_title, latest_job.company_name, latest_project.name)
        questions.append(
            ExpectedQuestion(
                question=prompt,
                suggested_answer=answer,
                keywords_to_listen_for=keywords,
                difficulty=difficulty,
            )
        )
    return questions


def _job_interview_answer(question: str, profile: CompleteUserProfile, company_name: str, role_title: str, latest_company: str, latest_project: str) -> str:
    strongest_skill = profile.skills[0].name
    second_skill = profile.skills[1].name
    achievement = profile.work_history[0].achievements[0].rstrip(".")
    return (
        f"For {question.lower()} I would anchor my answer in my {profile.identity.total_experience_years} years of experience, "
        f"especially using {strongest_skill} and {second_skill}. At {latest_company}, I {achievement}. "
        f"That gives me a practical example I can connect to {role_title} responsibilities and the work I delivered on {latest_project}."
    )


def _client_presentation_answer(question: str, profile: CompleteUserProfile, company_name: str, role_title: str, latest_company: str, latest_project: str) -> str:
    achievement = profile.work_history[0].achievements[0].rstrip(".")
    return (
        f"For {question.lower()} I'd point to concrete proof: on {latest_project}, {achievement.lower()}. "
        f"I'd tie that directly back to {company_name}'s goals and confirm the specific deliverable and timeline before moving on."
    )


def _product_demo_answer(question: str, profile: CompleteUserProfile, company_name: str, role_title: str, latest_company: str, latest_project: str) -> str:
    achievement = profile.work_history[0].achievements[0].rstrip(".")
    return (
        f"For {question.lower()} I'd demonstrate it live rather than describe it, using a scenario close to {company_name}'s workflow. "
        f"On {latest_project}, {achievement.lower()} -- that's the same kind of outcome this feature is built to repeat."
    )


def _team_meeting_answer(question: str, profile: CompleteUserProfile, company_name: str, role_title: str, latest_company: str, latest_project: str) -> str:
    achievement = profile.work_history[0].achievements[0].rstrip(".")
    return (
        f"For {question.lower()} I'd give a direct, no-fluff status update on {latest_project}: {achievement.lower()}. "
        f"Then I'd name the specific decision or support needed from the team so we leave with a clear next action."
    )


def _sales_call_answer(question: str, profile: CompleteUserProfile, company_name: str, role_title: str, latest_company: str, latest_project: str) -> str:
    achievement = profile.work_history[0].achievements[0].rstrip(".")
    return (
        f"For {question.lower()} I'd acknowledge the concern directly, then bring it back to proof: on {latest_project}, {achievement.lower()}. "
        f"I'd connect that outcome to what {company_name} is trying to achieve and confirm the next concrete step."
    )


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------

def _build_red_flags(session_type: str, company_name: str, role_title: str) -> list[str]:
    builders = {
        "job_interview": lambda: [
            f"If {company_name} cannot define success metrics for the {role_title} role.",
            "If interviewers dismiss collaboration, feedback, or ownership questions.",
            "If the role expects senior impact without matching scope or support.",
        ],
        "client_presentation": lambda: [
            f"If {company_name} can't articulate the outcome they actually need, not just the deliverable.",
            "If the timeline or budget is fixed but scope is still open-ended.",
            "If there's no clear decision-maker in the room to move the proposal forward.",
        ],
        "product_demo": lambda: [
            f"If the stakeholders who can approve a purchase for {company_name} aren't in the demo.",
            "If the audience keeps asking about a use case the product doesn't actually cover.",
            "If there's no clear next step offered by the end of the session.",
        ],
        "team_meeting": lambda: [
            "If a blocker keeps getting raised without anyone owning the resolution.",
            "If the meeting ends without a clear decision or next action.",
            f"If scope keeps expanding without {company_name} adjusting timeline or resources.",
        ],
        "sales_call": lambda: [
            "If the prospect can't name a budget, timeline, or decision-maker.",
            f"If {company_name}'s stated problem doesn't match what's actually being evaluated.",
            "If objections are being deflected instead of addressed directly.",
        ],
    }
    return builders.get(session_type, builders["job_interview"])()


def _default_company_values(company_name: str) -> list[str]:
    return [
        f"Strong ownership mindset aligned with {company_name}'s growth stage",
        "Clear communication and cross-functional collaboration",
        "Measured execution with visible customer or business impact",
    ]
