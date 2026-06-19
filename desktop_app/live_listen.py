"""Live call listen -> transcript -> answer pipeline for interview sessions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .answer_builder import AnswerEngine, build_answer_engine, generate_answer_with_languages
from .language_config import get_listen_language_code, get_reply_language_code
from .audio_handler import AudioCapture, microphone_capture_status, record_until_silence
from .config_manager import load_runtime_config
from .interview_mode import _transcript_missing
from .utils import sanitize_display_text
from .onboarding import PROFILE_FILENAME, load_completed_profile
from .overlay import OverlayState, build_answer_overlay, build_listening_overlay
from .runtime_controller import (
    find_session_registry_entry,
    load_registered_session_state,
    update_registered_session_state,
)
from .stt_engine import STTEngine, build_stt_engine
from .strategy_generator import StrategyPack, load_strategy_pack


@dataclass
class LiveListenResult:
    transcript: str
    suggested_answer: str
    alternatives: list[str]
    provider_status: str
    confidence_score: int
    overlay_state: OverlayState
    audio_source: str = ""


def run_live_listen_cycle(
    session_id: str,
    registry_path: str | Path | None = None,
    max_seconds: float = 12.0,
    transcript_text: str | None = None,
    listen_language: str | None = None,
    reply_language: str | None = None,
) -> LiveListenResult:
    """Capture call audio (or use provided transcript), transcribe, and generate overlay answer."""
    entry = find_session_registry_entry(session_id, registry_path)
    profile_directory = Path(str(entry["profile_directory"]))
    strategy_path = profile_directory / "strategy_pack.json"
    strategy_pack = _load_strategy_pack_for_session(profile_directory, strategy_path, entry)

    runtime_config = load_runtime_config()
    listen_code = listen_language or get_listen_language_code()
    reply_code = reply_language or get_reply_language_code()
    stt_engine = build_stt_engine(runtime_config.model, language=listen_code)
    answer_engine = build_answer_engine(runtime_config.model)

    if transcript_text is not None and transcript_text.strip():
        audio_capture = AudioCapture(
            raw_audio=b"",
            started_at="",
            stopped_at="",
            duration_seconds=0.0,
            transcript_hint=transcript_text.strip(),
            source="browser_transcript",
        )
    else:
        mic_status = microphone_capture_status()
        if not bool(mic_status.get("can_capture", False)):
            raise RuntimeError(str(mic_status.get("message", "Live microphone capture is unavailable.")))
        audio_capture = record_until_silence(max_seconds=max_seconds, prefer_call_audio=True)
        if not audio_capture.raw_audio.strip(b"\x00"):
            raise RuntimeError(
                "No speech detected on the PC microphone. Speak clearly near the laptop mic, "
                "or enable Stereo Mix to capture Zoom/WhatsApp call audio."
            )

    return _finalize_live_capture(
        session_id=session_id,
        registry_path=registry_path,
        strategy_pack=strategy_pack,
        audio_capture=audio_capture,
        stt_engine=stt_engine,
        answer_engine=answer_engine,
        listen_language=listen_code,
        reply_language=reply_code,
    )


def _finalize_live_capture(
    session_id: str,
    registry_path: str | Path | None,
    strategy_pack: StrategyPack,
    audio_capture: AudioCapture,
    stt_engine: STTEngine,
    answer_engine: AnswerEngine,
    listen_language: str | None = None,
    reply_language: str | None = None,
) -> LiveListenResult:
    transcript_result = stt_engine.transcribe(audio_capture)
    raw_transcript = transcript_result.transcript.strip()
    transcript = raw_transcript
    if not _transcript_missing(raw_transcript):
        cleaned = sanitize_display_text(raw_transcript, fallback=raw_transcript)
        if cleaned:
            transcript = cleaned

    if _transcript_missing(transcript):
        suggested_answer = "Could not hear clearly, please type manually"
        alternatives = [
            "Please repeat the question clearly.",
            "Type the question in Manual Input as a backup.",
        ]
        lowered = transcript.casefold()
        if "real stt provider required" in lowered:
            provider_status = "Speech-to-text not installed — rebuild and reinstall the desktop app"
        elif "not clear enough" in lowered or "no speech detected" in lowered:
            provider_status = "Speech unclear — speak closer to PC mic or type the question manually"
        else:
            provider_status = "Transcript unavailable — speak closer to PC mic"
        confidence_score = strategy_pack.confidence.score
    else:
        answer_result = generate_answer_with_languages(
            transcript,
            strategy_pack,
            answer_engine,
            listen_language=listen_language or get_listen_language_code(),
            reply_language=reply_language or get_reply_language_code(),
        )
        suggested_answer = answer_result.suggested_answer
        alternatives = answer_result.alternatives
        provider_status = answer_result.provider_name
        confidence_score = strategy_pack.confidence.score

    overlay_state = build_answer_overlay(
        transcript=transcript,
        suggested_answer=suggested_answer,
        alternatives=alternatives,
        confidence_score=confidence_score,
        provider_status=provider_status,
    )

    existing_state = load_registered_session_state(session_id, registry_path)
    update_registered_session_state(
        session_id,
        {
            **existing_state,
            "overlay_status": overlay_state.status,
            "overlay_visible": True,
            "transcript": transcript,
            "suggested_answer": suggested_answer,
            "alternatives": alternatives,
            "provider_status": provider_status,
            "confidence_score": confidence_score,
            "last_answer": suggested_answer,
            "last_transcript": transcript,
            "audio_source": audio_capture.source,
            "listen_language": listen_language or get_listen_language_code(),
            "reply_language": reply_language or get_reply_language_code(),
        },
        registry_path=registry_path,
    )

    return LiveListenResult(
        transcript=transcript,
        suggested_answer=suggested_answer,
        alternatives=alternatives,
        provider_status=provider_status,
        confidence_score=confidence_score,
        overlay_state=overlay_state,
        audio_source=audio_capture.source,
    )


def build_listening_state_for_session(session_id: str, registry_path: str | Path | None = None) -> OverlayState:
    existing_state = load_registered_session_state(session_id, registry_path)
    update_registered_session_state(
        session_id,
        {**existing_state, "overlay_status": "listening", "overlay_visible": True},
        registry_path=registry_path,
    )
    return build_listening_overlay()


def _load_strategy_pack_for_session(
    profile_directory: Path,
    strategy_path: Path,
    entry: dict[str, object],
) -> StrategyPack:
    if strategy_path.exists():
        return load_strategy_pack(strategy_path)

    profile = load_completed_profile(profile_directory / PROFILE_FILENAME)
    from .strategy_generator import generate_strategy_pack

    return generate_strategy_pack(
        profile,
        company_name=str(entry.get("company_name", "Target Company") or "Target Company"),
        role_title=str(entry.get("role_title", "Target Role") or "Target Role"),
    )
