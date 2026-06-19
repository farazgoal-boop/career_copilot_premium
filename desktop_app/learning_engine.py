"""Post-interview learning reports and profile update insights."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re

from .interview_mode import InterviewTurn
from .onboarding import CompleteUserProfile

FILLER_WORDS = {"umm", "um", "uh", "like", "hmm"}


@dataclass
class ReportTurn:
    question: str
    suggested_answer: str
    actual_answer: str
    response_seconds: float


@dataclass
class MistakeAnalysis:
    findings: list[str]
    filler_word_count: int


@dataclass
class WeakEnglishReport:
    avoided_words: list[str]
    grammar_patterns_missed: list[str]
    suggested_daily_practice: str


@dataclass
class UpdatedProfileInsights:
    new_questions_encountered: list[str]
    answers_that_worked_well: list[str]
    areas_needing_improvement: list[str]


@dataclass
class LearningReport:
    created_at: str
    transcript: list[ReportTurn]
    mistake_analysis: MistakeAnalysis
    weak_english: WeakEnglishReport
    improvement_plan: list[str]
    updated_profile: UpdatedProfileInsights

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_learning_report(profile: CompleteUserProfile, turns: list[InterviewTurn]) -> LearningReport:
    report_turns = [
        ReportTurn(
            question=turn.transcript,
            suggested_answer=turn.suggested_answer,
            actual_answer=turn.actual_answer,
            response_seconds=turn.response_seconds,
        )
        for turn in turns
    ]

    mistake_analysis = _build_mistake_analysis(turns)
    weak_english = _build_weak_english_report(turns)
    improvement_plan = _build_improvement_plan(turns)
    updated_profile = _build_updated_profile(profile, turns)

    return LearningReport(
        created_at=_utc_now_iso(),
        transcript=report_turns,
        mistake_analysis=mistake_analysis,
        weak_english=weak_english,
        improvement_plan=improvement_plan,
        updated_profile=updated_profile,
    )


def _build_mistake_analysis(turns: list[InterviewTurn]) -> MistakeAnalysis:
    findings: list[str] = []
    filler_count = 0

    for turn in turns:
        actual_answer = turn.actual_answer.strip()
        filler_count += _count_filler_words(actual_answer)

        if not actual_answer:
            findings.append(f"You did not capture what you actually said for question about '{turn.transcript}'.")
            continue

        if len(actual_answer.split()) < max(8, len(turn.suggested_answer.split()) // 3):
            findings.append(f"You hesitated or answered too briefly on question about '{turn.transcript}'.")

        if turn.response_seconds > 8:
            findings.append(f"You took {turn.response_seconds:.1f}s to answer '{turn.transcript}', so practice a faster opening.")

        improvement_word = _first_missing_keyword(turn.suggested_answer, actual_answer)
        if improvement_word:
            findings.append(
                f"Your answer for '{turn.transcript}' could be stronger by mentioning {improvement_word}."
            )

    if filler_count:
        findings.append(f"You used filler words like 'umm' {filler_count} times.")

    return MistakeAnalysis(findings=findings, filler_word_count=filler_count)


def _build_weak_english_report(turns: list[InterviewTurn]) -> WeakEnglishReport:
    avoided_words: list[str] = []
    grammar_patterns_missed: list[str] = []

    for turn in turns:
        avoided_words.extend(_find_avoided_words(turn.suggested_answer, turn.actual_answer))
        if turn.actual_answer and not turn.actual_answer[:1].isupper():
            grammar_patterns_missed.append("Sentence openings were not consistently clear or well-formed.")
        if turn.actual_answer and " i " in f" {turn.actual_answer} ":
            grammar_patterns_missed.append("The pronoun 'I' was not consistently capitalized.")

    unique_avoided_words = _unique_preserve_order(avoided_words)[:5]
    unique_grammar = _unique_preserve_order(grammar_patterns_missed)[:3]
    if not unique_grammar:
        unique_grammar.append("Keep answers concise with one strong opening sentence and one evidence sentence.")

    return WeakEnglishReport(
        avoided_words=unique_avoided_words,
        grammar_patterns_missed=unique_grammar,
        suggested_daily_practice="Spend 5 minutes daily recording one answer, then remove filler words and tighten the first two sentences.",
    )


def _build_improvement_plan(turns: list[InterviewTurn]) -> list[str]:
    plan: list[str] = []
    for turn in turns[:5]:
        plan.append(
            f"Practice '{turn.transcript}' and use this answer: {turn.suggested_answer}"
        )
    return plan


def _build_updated_profile(profile: CompleteUserProfile, turns: list[InterviewTurn]) -> UpdatedProfileInsights:
    known_topics = {skill.name.lower() for skill in profile.skills}
    new_questions = [turn.transcript for turn in turns if not any(topic in turn.transcript.lower() for topic in known_topics)]
    strong_answers = [
        turn.transcript
        for turn in turns
        if turn.actual_answer and len(turn.actual_answer.split()) >= 10 and _count_filler_words(turn.actual_answer) == 0
    ]
    improvement_areas = _unique_preserve_order(
        [
            finding.split(" about ")[-1].strip("'.")
            for finding in _build_mistake_analysis(turns).findings
            if "about '" in finding
        ]
    )
    if not improvement_areas:
        improvement_areas = profile.weaknesses.technical_weak_areas[:2]

    return UpdatedProfileInsights(
        new_questions_encountered=_unique_preserve_order(new_questions)[:5],
        answers_that_worked_well=strong_answers[:5],
        areas_needing_improvement=improvement_areas[:5],
    )


def _count_filler_words(answer: str) -> int:
    tokens = re.findall(r"[a-z']+", answer.lower())
    return sum(1 for token in tokens if token in FILLER_WORDS)


def _find_avoided_words(suggested_answer: str, actual_answer: str) -> list[str]:
    suggested_tokens = [token for token in re.findall(r"[a-z]+", suggested_answer.lower()) if len(token) >= 8]
    actual_token_set = set(re.findall(r"[a-z]+", actual_answer.lower()))
    return [token for token in suggested_tokens if token not in actual_token_set]


def _first_missing_keyword(suggested_answer: str, actual_answer: str) -> str | None:
    avoided = _find_avoided_words(suggested_answer, actual_answer)
    return avoided[0] if avoided else None


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()