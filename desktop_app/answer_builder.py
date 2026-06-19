"""Answer generation and fallback rendering for live interview mode."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Protocol
from urllib import error, request

from .config_manager import ModelConfig, load_runtime_config
from .strategy_generator import (
    CompanyResearchBrief,
    ExpectedQuestion,
    PersonalizedAnswerTemplates,
    StrategyPack,
)


@dataclass
class AnswerResult:
    suggested_answer: str
    alternatives: list[str]
    provider_name: str


class AnswerEngine(Protocol):
    def generate_answer(self, transcript: str, strategy_pack: StrategyPack) -> AnswerResult:
        ...


class DeterministicAnswerEngine:
    def generate_answer(self, transcript: str, strategy_pack: StrategyPack) -> AnswerResult:
        return _build_deterministic_answer(transcript, strategy_pack)


class OllamaAnswerEngine:
    def __init__(
        self,
        model_name: str,
        fallback_engine: AnswerEngine | None = None,
        base_url: str = "http://127.0.0.1:11434/api/generate",
        timeout_seconds: float = 8.0,
    ) -> None:
        self.model_name = model_name
        self.fallback_engine = fallback_engine
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def generate_answer(self, transcript: str, strategy_pack: StrategyPack) -> AnswerResult:
        matched_question = _select_best_expected_question(transcript, strategy_pack.expected_questions)
        prompt = _build_provider_prompt(transcript, matched_question, strategy_pack)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }

        try:
            generated_text = _request_ollama_answer(
                base_url=self.base_url,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
        except (OSError, ValueError, error.URLError):
            if self.fallback_engine is None:
                raise
            fallback_result = self.fallback_engine.generate_answer(transcript, strategy_pack)
            return AnswerResult(
                suggested_answer=fallback_result.suggested_answer,
                alternatives=fallback_result.alternatives,
                provider_name=f"Ollama({self.model_name}) -> {fallback_result.provider_name}",
            )

        cleaned_answer = simplify_answer(generated_text.strip())
        if not cleaned_answer:
            if self.fallback_engine is None:
                raise ValueError("Ollama returned an empty answer.")
            return self.fallback_engine.generate_answer(transcript, strategy_pack)

        return AnswerResult(
            suggested_answer=cleaned_answer,
            alternatives=build_alternative_answers(cleaned_answer, strategy_pack),
            provider_name=f"Ollama({self.model_name})",
        )


class OpenAICompatibleAnswerEngine:
    def __init__(
        self,
        model_name: str,
        base_url: str,
        api_key_env: str = "OPENAI_API_KEY",
        fallback_engine: AnswerEngine | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.fallback_engine = fallback_engine
        self.timeout_seconds = timeout_seconds

    def generate_answer(self, transcript: str, strategy_pack: StrategyPack) -> AnswerResult:
        matched_question = _select_best_expected_question(transcript, strategy_pack.expected_questions)
        prompt = _build_provider_prompt(transcript, matched_question, strategy_pack)
        api_key = os.environ.get(self.api_key_env, "").strip()
        if not api_key:
            if self.fallback_engine is None:
                raise RuntimeError(f"Missing API key environment variable: {self.api_key_env}")
            fallback_result = self.fallback_engine.generate_answer(transcript, strategy_pack)
            return AnswerResult(
                suggested_answer=fallback_result.suggested_answer,
                alternatives=fallback_result.alternatives,
                provider_name=f"OpenAICompatible({self.model_name}) -> {fallback_result.provider_name}",
            )

        try:
            generated_text = _request_openai_compatible_answer(
                base_url=self.base_url,
                model_name=self.model_name,
                prompt=prompt,
                api_key=api_key,
                timeout_seconds=self.timeout_seconds,
            )
        except (OSError, ValueError, RuntimeError, error.URLError):
            if self.fallback_engine is None:
                raise
            fallback_result = self.fallback_engine.generate_answer(transcript, strategy_pack)
            return AnswerResult(
                suggested_answer=fallback_result.suggested_answer,
                alternatives=fallback_result.alternatives,
                provider_name=f"OpenAICompatible({self.model_name}) -> {fallback_result.provider_name}",
            )

        cleaned_answer = simplify_answer(generated_text.strip())
        if not cleaned_answer:
            if self.fallback_engine is None:
                raise ValueError("OpenAI-compatible provider returned an empty answer.")
            return self.fallback_engine.generate_answer(transcript, strategy_pack)

        return AnswerResult(
            suggested_answer=cleaned_answer,
            alternatives=build_alternative_answers(cleaned_answer, strategy_pack),
            provider_name=f"OpenAICompatible({self.model_name})",
        )


def build_manual_strategy_pack(question: str = "") -> StrategyPack:
    """Minimal strategy pack for overlay manual input (no saved profile required)."""
    from .confidence_validator import assess_interview_confidence
    from .fallback_manager import build_fallback_plan
    from .onboarding import CompleteUserProfile, IdentitySetup, ProjectPortfolioEntry, ResumeConfirmation, SkillEntry, TargetJobProfile, WeaknessProfile, WorkHistoryEntry

    placeholder_question = question.strip() or "Tell me about yourself."
    profile = CompleteUserProfile(
        identity=IdentitySetup(
            full_name="Candidate",
            current_role="Professional",
            total_experience_years=4,
            location="Remote",
            work_mode="Hybrid",
        ),
        skills=[
            SkillEntry(name="Communication", level="Expert"),
            SkillEntry(name="Problem Solving", level="Expert"),
            SkillEntry(name="Delivery", level="Intermediate"),
        ],
        work_history=[
            WorkHistoryEntry(
                company_name="Recent Role",
                duration="Current",
                achievements=[
                    "Delivered measurable results under deadline pressure.",
                    "Collaborated across teams to ship reliable solutions.",
                ],
                reason_for_leaving="Seeking new challenge.",
                salary_expectations="Open.",
            )
        ],
        projects=[
            ProjectPortfolioEntry(
                name="Recent project",
                description="Hands-on delivery with measurable impact.",
                technologies=["Python"],
                contribution="Owned delivery end to end.",
                link=None,
            )
        ],
        resume=ResumeConfirmation(
            filename="manual-input.txt",
            extracted_text=placeholder_question,
            confirmed=True,
            source_format="text",
        ),
        weaknesses=WeaknessProfile(
            english_fluency_level=7,
            technical_weak_areas=["Live pressure"],
            interview_anxiety_level=4,
            previous_interview_failures="",
            improvement_actions=["Keep answers concise and confident."],
        ),
        target_job=TargetJobProfile(
            job_title="Target Role",
            industry="Technology",
            company_type="Corporate",
            interview_difficulty="Mid",
        ),
        profile_version="1.0",
        created_at="",
        updated_at="",
    )
    expected = ExpectedQuestion(
        question=placeholder_question,
        suggested_answer=(
            "I bring practical experience, clear communication, and ownership. "
            "In my recent work I delivered reliable results and stayed calm under pressure."
        ),
        keywords_to_listen_for=_tokenize(placeholder_question)[:6],
        difficulty="Mid",
    )
    templates = PersonalizedAnswerTemplates(
        tell_me_about_yourself=expected.suggested_answer,
        why_should_we_hire_you=expected.suggested_answer,
        what_is_your_weakness="I focus on concise delivery and continuous improvement.",
    )
    return StrategyPack(
        company_brief=CompanyResearchBrief(
            company_name="Interview",
            role_title="Target Role",
            common_questions=[placeholder_question],
            company_values=["Ownership", "Clarity"],
            red_flags=[],
        ),
        answer_templates=templates,
        expected_questions=[expected],
        fallback_plan=build_fallback_plan(),
        confidence=assess_interview_confidence(profile, "Target Role"),
    )


def generate_manual_answer(
    question: str,
    model_config: ModelConfig | None = None,
    listen_language: str | None = None,
    reply_language: str | None = None,
) -> AnswerResult:
    """Generate an overlay answer for typed manual input using the configured LLM."""
    from runtime_paths import load_env_file

    load_env_file()
    config = model_config or load_runtime_config().model
    engine = build_answer_engine(config)
    strategy_pack = build_manual_strategy_pack(question)
    return generate_answer_with_languages(
        question,
        strategy_pack,
        engine,
        listen_language=listen_language,
        reply_language=reply_language,
    )


def generate_answer_with_languages(
    transcript: str,
    strategy_pack: StrategyPack,
    engine: AnswerEngine,
    listen_language: str | None = None,
    reply_language: str | None = None,
) -> AnswerResult:
    from .language_config import get_listen_language_code, get_reply_language_code, language_label_for_code

    listen_code = listen_language or get_listen_language_code()
    reply_code = reply_language or get_reply_language_code()
    matched_question = _select_best_expected_question(transcript, strategy_pack.expected_questions)
    prompt = _build_language_aware_prompt(
        transcript=transcript,
        matched_question=matched_question,
        strategy_pack=strategy_pack,
        listen_language=language_label_for_code(listen_code),
        reply_language=language_label_for_code(reply_code),
    )
    if isinstance(engine, ChainedAnswerEngine):
        for child in engine.engines:
            try:
                result = _generate_from_prompt(child, prompt, strategy_pack, transcript)
                if result.suggested_answer.strip():
                    return result
            except Exception:
                continue
        return DeterministicAnswerEngine().generate_answer(transcript, strategy_pack)
    return _generate_from_prompt(engine, prompt, strategy_pack, transcript)


def _generate_from_prompt(
    engine: AnswerEngine,
    prompt: str,
    strategy_pack: StrategyPack,
    transcript: str,
) -> AnswerResult:
    if isinstance(engine, OllamaAnswerEngine):
        return _generate_ollama_with_prompt(engine, prompt, strategy_pack, transcript)
    if isinstance(engine, OpenAICompatibleAnswerEngine):
        return _generate_openai_with_prompt(engine, prompt, strategy_pack, transcript)
    return engine.generate_answer(transcript, strategy_pack)


def build_live_answer(transcript: str, strategy_pack: StrategyPack) -> tuple[str, list[str]]:
    result = _build_deterministic_answer(transcript, strategy_pack)
    return result.suggested_answer, result.alternatives


class ChainedAnswerEngine:
    """Try engines in order until one produces an answer."""

    def __init__(self, engines: list[AnswerEngine], label: str = "ChainedAnswerEngine") -> None:
        self.engines = engines
        self.label = label

    def generate_answer(self, transcript: str, strategy_pack: StrategyPack) -> AnswerResult:
        last_error: Exception | None = None
        for engine in self.engines:
            try:
                result = engine.generate_answer(transcript, strategy_pack)
                if result.suggested_answer.strip():
                    return result
            except Exception as error:  # noqa: BLE001 - try next provider in chain
                last_error = error
                continue
        if last_error is not None:
            raise last_error
        return DeterministicAnswerEngine().generate_answer(transcript, strategy_pack)


def _append_llm_engine(
    engines: list[AnswerEngine],
    *,
    model_name: str,
    base_url: str,
    api_key_env: str,
    timeout_seconds: float,
) -> None:
    normalized = model_name.strip().lower()
    if not normalized:
        return
    if normalized.startswith("ollama:") or normalized.startswith("llama"):
        resolved = model_name.split(":", 1)[1].strip() if ":" in model_name else model_name
        engines.append(
            OllamaAnswerEngine(
                model_name=resolved or "llama3.2:3b",
                fallback_engine=None,
                base_url=base_url,
                timeout_seconds=timeout_seconds,
            )
        )
        return
    if normalized.startswith("openai:") or normalized.startswith("mistral"):
        resolved = model_name.split(":", 1)[1].strip() if ":" in model_name else model_name
        engines.append(
            OpenAICompatibleAnswerEngine(
                model_name=resolved,
                base_url=base_url,
                api_key_env=api_key_env,
                fallback_engine=None,
                timeout_seconds=timeout_seconds,
            )
        )


def build_answer_engine(model_config: ModelConfig) -> AnswerEngine:
    deterministic_engine = DeterministicAnswerEngine()
    engines: list[AnswerEngine] = []
    api_key = os.environ.get(model_config.llm_api_key_env, "").strip()

    primary_model = model_config.llm_model.strip()
    fallback_model = getattr(model_config, "llm_fallback_model", "").strip()
    primary_is_cloud = primary_model.casefold().startswith(("mistral", "openai:"))
    fallback_is_cloud = fallback_model.casefold().startswith(("mistral", "openai:"))

    # Prefer cloud LLM first when a client API key is available (typical buyer setup).
    if api_key:
        if primary_is_cloud:
            _append_llm_engine(
                engines,
                model_name=primary_model,
                base_url=model_config.llm_base_url,
                api_key_env=model_config.llm_api_key_env,
                timeout_seconds=model_config.llm_timeout_seconds,
            )
        if fallback_is_cloud and fallback_model.casefold() != primary_model.casefold():
            _append_llm_engine(
                engines,
                model_name=fallback_model,
                base_url=getattr(
                    model_config,
                    "llm_fallback_base_url",
                    "https://api.mistral.ai/v1/chat/completions",
                ),
                api_key_env=model_config.llm_api_key_env,
                timeout_seconds=model_config.llm_timeout_seconds,
            )

    if primary_model and not primary_is_cloud:
        _append_llm_engine(
            engines,
            model_name=primary_model,
            base_url=model_config.llm_base_url,
            api_key_env=model_config.llm_api_key_env,
            timeout_seconds=model_config.llm_timeout_seconds,
        )
    if fallback_model and not fallback_is_cloud and fallback_model.casefold() != primary_model.casefold():
        _append_llm_engine(
            engines,
            model_name=fallback_model,
            base_url=getattr(
                model_config,
                "llm_fallback_base_url",
                "http://127.0.0.1:11434/api/generate",
            ),
            api_key_env=model_config.llm_api_key_env,
            timeout_seconds=model_config.llm_timeout_seconds,
        )

    if model_config.offline_fallback_enabled:
        engines.append(deterministic_engine)

    if not engines:
        return deterministic_engine
    if len(engines) == 1:
        return engines[0]
    return ChainedAnswerEngine(engines)


def _build_deterministic_answer(transcript: str, strategy_pack: StrategyPack) -> AnswerResult:
    matched_question = _select_best_expected_question(transcript, strategy_pack.expected_questions)
    overlap = len(set(_tokenize(transcript)) & set(_tokenize(matched_question.question)))
    if overlap >= 2:
        base_answer = matched_question.suggested_answer
    else:
        base_answer = (
            f"On your question about {transcript}, my strongest fit is "
            f"{strategy_pack.answer_templates.why_should_we_hire_you}"
        )
    simple_answer = simplify_answer(base_answer)
    alternatives = build_alternative_answers(base_answer, strategy_pack)
    return AnswerResult(
        suggested_answer=simple_answer,
        alternatives=alternatives,
        provider_name="DeterministicAnswerEngine",
    )


def simplify_answer(answer: str) -> str:
    shortened = answer.replace("responsibilities", "work").replace("practical example", "real example")
    sentences = [segment.strip() for segment in shortened.split(". ") if segment.strip()]
    return ". ".join(sentences[:2]).strip()


def build_alternative_answers(answer: str, strategy_pack: StrategyPack) -> list[str]:
    alternatives = [
        f"Short version: {simplify_answer(answer)}",
        (
            "Impact version: "
            f"{strategy_pack.answer_templates.why_should_we_hire_you}"
        ),
    ]
    return alternatives


def _build_provider_prompt(
    transcript: str,
    matched_question: ExpectedQuestion,
    strategy_pack: StrategyPack,
) -> str:
    return _build_language_aware_prompt(
        transcript=transcript,
        matched_question=matched_question,
        strategy_pack=strategy_pack,
        listen_language="English",
        reply_language="English",
    )


def _build_language_aware_prompt(
    transcript: str,
    matched_question: ExpectedQuestion,
    strategy_pack: StrategyPack,
    listen_language: str,
    reply_language: str,
) -> str:
    overlap = len(set(_tokenize(transcript)) & set(_tokenize(matched_question.question)))
    reference_block = ""
    if overlap >= 2:
        reference_block = (
            f"\nPrepared talking points (use only if relevant):\n"
            f"- {matched_question.suggested_answer}\n"
            f"- {strategy_pack.answer_templates.why_should_we_hire_you}\n"
        )
    return (
        "You are a live interview coach. Write the candidate's spoken reply.\n"
        f"Interviewer question ({listen_language}): \"{transcript}\"\n"
        f"Reply language: {reply_language}\n"
        f"Role: {strategy_pack.company_brief.role_title} at {strategy_pack.company_brief.company_name}\n"
        "Rules:\n"
        "- Answer ONLY the interviewer question above.\n"
        "- Do not change topic or answer a different question.\n"
        "- First person, confident, natural speech, 50-90 words.\n"
        "- Use the candidate's real experience from the talking points when relevant.\n"
        f"{reference_block}"
        "Respond with only the answer text. No labels, no quotes."
    )


def _generate_ollama_with_prompt(
    engine: OllamaAnswerEngine,
    prompt: str,
    strategy_pack: StrategyPack,
    transcript: str,
) -> AnswerResult:
    payload = {"model": engine.model_name, "prompt": prompt, "stream": False}
    try:
        generated_text = _request_ollama_answer(
            base_url=engine.base_url,
            payload=payload,
            timeout_seconds=engine.timeout_seconds,
        )
    except (OSError, ValueError, error.URLError):
        if engine.fallback_engine is None:
            raise
        return engine.fallback_engine.generate_answer(transcript, strategy_pack)
    cleaned_answer = simplify_answer(generated_text.strip())
    if not cleaned_answer:
        if engine.fallback_engine is None:
            raise ValueError("Ollama returned an empty answer.")
        return engine.fallback_engine.generate_answer(transcript, strategy_pack)
    return AnswerResult(
        suggested_answer=cleaned_answer,
        alternatives=build_alternative_answers(cleaned_answer, strategy_pack),
        provider_name=f"Ollama({engine.model_name})",
    )


def _generate_openai_with_prompt(
    engine: OpenAICompatibleAnswerEngine,
    prompt: str,
    strategy_pack: StrategyPack,
    transcript: str,
) -> AnswerResult:
    api_key = os.environ.get(engine.api_key_env, "").strip()
    if not api_key:
        if engine.fallback_engine is None:
            raise RuntimeError(f"Missing API key environment variable: {engine.api_key_env}")
        return engine.fallback_engine.generate_answer(transcript, strategy_pack)
    try:
        generated_text = _request_openai_compatible_answer(
            base_url=engine.base_url,
            model_name=engine.model_name,
            prompt=prompt,
            api_key=api_key,
            timeout_seconds=engine.timeout_seconds,
        )
    except (OSError, ValueError, RuntimeError, error.URLError):
        if engine.fallback_engine is None:
            raise
        return engine.fallback_engine.generate_answer(transcript, strategy_pack)
    cleaned_answer = simplify_answer(generated_text.strip())
    if not cleaned_answer:
        if engine.fallback_engine is None:
            raise ValueError("OpenAI-compatible provider returned an empty answer.")
        return engine.fallback_engine.generate_answer(transcript, strategy_pack)
    display_name = "Mistral" if "mistral" in engine.model_name.casefold() else engine.model_name
    return AnswerResult(
        suggested_answer=cleaned_answer,
        alternatives=build_alternative_answers(cleaned_answer, strategy_pack),
        provider_name=f"Mistral({engine.model_name})" if display_name == "Mistral" else f"OpenAICompatible({engine.model_name})",
    )


def _request_ollama_answer(base_url: str, payload: dict[str, object], timeout_seconds: float) -> str:
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        base_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=timeout_seconds) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    generated_text = str(response_payload.get("response", "")).strip()
    if not generated_text:
        raise ValueError("Ollama response did not include generated text.")
    return generated_text


def _request_openai_compatible_answer(
    base_url: str,
    model_name: str,
    prompt: str,
    api_key: str,
    timeout_seconds: float,
) -> str:
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        base_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with request.urlopen(http_request, timeout=timeout_seconds) as response:
        response_payload = json.loads(response.read().decode("utf-8"))

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI-compatible response did not include choices.")

    message = choices[0].get("message", {})
    generated_text = str(message.get("content", "")).strip()
    if not generated_text:
        raise ValueError("OpenAI-compatible response did not include generated text.")
    return generated_text


def _select_best_expected_question(transcript: str, expected_questions: list[ExpectedQuestion]) -> ExpectedQuestion:
    transcript_tokens = set(_tokenize(transcript))
    best_question = expected_questions[0]
    best_score = -1

    for candidate in expected_questions:
        candidate_tokens = set(_tokenize(candidate.question))
        score = len(transcript_tokens & candidate_tokens)
        if score > best_score:
            best_question = candidate
            best_score = score
    return best_question


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())