"""Desktop interview mode orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .answer_builder import AnswerEngine, DeterministicAnswerEngine, build_alternative_answers
from .audio_handler import AudioCapture, AudioRecorder, ScriptedAudioRecorder
from .hotkeys import HotkeyManager
from .onboarding import is_session_ready
from .overlay import OverlayState, build_answer_overlay, build_listening_overlay
from .stt_engine import STTEngine, ScriptedSTTEngine
from .strategy_generator import StrategyPack
from .vad import analyze_audio_capture


_NO_TRANSCRIPT_SENTINELS = {
    "audio captured. whisper returned no transcript.",
    "audio captured. real stt provider required.",
}


@dataclass
class InterviewTurn:
    transcript: str
    suggested_answer: str
    alternatives: list[str]
    confidence_score: int
    actual_answer: str = ""
    response_seconds: float = 0.0


class DesktopInterviewMode:
    def __init__(
        self,
        profile_directory: str | Path,
        strategy_pack: StrategyPack,
        audio_recorder: AudioRecorder | None = None,
        stt_engine: STTEngine | None = None,
        answer_engine: AnswerEngine | None = None,
        hotkey_manager: HotkeyManager | None = None,
        overlay_opacity: float = 0.7,
        hotkey: str = "F2",
    ) -> None:
        self.profile_directory = Path(profile_directory)
        self.strategy_pack = strategy_pack
        self.audio_recorder: AudioRecorder = audio_recorder or ScriptedAudioRecorder()
        self.stt_engine: STTEngine = stt_engine or ScriptedSTTEngine()
        self.answer_engine: AnswerEngine = answer_engine or DeterministicAnswerEngine()
        self.hotkey_manager = hotkey_manager or HotkeyManager()
        self.overlay_opacity = overlay_opacity
        self.hotkey = hotkey
        self.overlay_state = OverlayState(status="idle", opacity=overlay_opacity, visible=False)
        self.last_turn: InterviewTurn | None = None
        self.session_turns: list[InterviewTurn] = []

        self.hotkey_manager.register(self.hotkey, self.toggle_recording)

    def shutdown(self) -> None:
        self.hotkey_manager.shutdown()

    def ensure_ready(self) -> None:
        if not is_session_ready(self.profile_directory):
            raise PermissionError("Interview mode is locked until a resume-backed profile is ready.")

    def toggle_recording(self) -> OverlayState:
        self.ensure_ready()

        if not self.audio_recorder.is_recording:
            self.audio_recorder.start_recording()
            self.overlay_state = build_listening_overlay(opacity=self.overlay_opacity)
            return self.overlay_state

        audio_capture = self.audio_recorder.stop_recording()
        return self._finalize_audio_capture(audio_capture)

    def handle_auto_stop(self, audio_capture: AudioCapture) -> OverlayState:
        self.ensure_ready()
        decision = analyze_audio_capture(audio_capture)
        if not decision.should_auto_stop:
            self.overlay_state = build_listening_overlay(opacity=self.overlay_opacity)
            return self.overlay_state

        return self._finalize_audio_capture(audio_capture)

    def _finalize_audio_capture(self, audio_capture: AudioCapture) -> OverlayState:
        transcript_result = self.stt_engine.transcribe(audio_capture)
        transcript_text = transcript_result.transcript.strip()

        if _transcript_missing(transcript_text):
            suggested_answer = "I could not catch the question clearly. Please repeat the question in one short sentence."
            alternatives = [
                "Please repeat the question clearly.",
                "Could you say that again in one short line?",
            ]
            provider_status = "Transcript unavailable"
        else:
            answer_result = self.answer_engine.generate_answer(transcript_text, self.strategy_pack)
            suggested_answer = answer_result.suggested_answer
            alternatives = answer_result.alternatives
            provider_status = answer_result.provider_name

        self.last_turn = InterviewTurn(
            transcript=transcript_text,
            suggested_answer=suggested_answer,
            alternatives=alternatives,
            confidence_score=self.strategy_pack.confidence.score,
        )
        self.session_turns.append(self.last_turn)
        self.overlay_state = build_answer_overlay(
            transcript=transcript_text,
            suggested_answer=suggested_answer,
            alternatives=alternatives,
            confidence_score=self.strategy_pack.confidence.score,
            provider_status=provider_status,
            opacity=self.overlay_opacity,
        )
        return self.overlay_state

    def record_actual_answer(self, actual_answer: str, response_seconds: float) -> InterviewTurn:
        if self.last_turn is None:
            raise RuntimeError("No interview turn is available to record the user's answer.")

        self.last_turn.actual_answer = actual_answer.strip()
        self.last_turn.response_seconds = response_seconds
        return self.last_turn

    def apply_fallback(self, action: str) -> OverlayState:
        if self.last_turn is None:
            raise RuntimeError("No interview turn is available for fallback actions.")

        fallback_action = action.lower()
        if fallback_action == "simple":
            answer = self.last_turn.suggested_answer
        elif fallback_action == "alternatives":
            answer = self.last_turn.alternatives[0]
        else:
            answer = self.strategy_pack.fallback_plan[fallback_action]

        alternatives = build_alternative_answers(answer, self.strategy_pack)
        self.overlay_state = build_answer_overlay(
            transcript=self.last_turn.transcript,
            suggested_answer=answer,
            alternatives=alternatives,
            confidence_score=self.last_turn.confidence_score,
            provider_status=self.overlay_state.provider_status,
            opacity=self.overlay_opacity,
        )
        return self.overlay_state


def _transcript_missing(transcript: str) -> bool:
    normalized = transcript.strip().casefold()
    if not normalized:
        return True
    if normalized in _NO_TRANSCRIPT_SENTINELS:
        return True
    if normalized.startswith("audio captured.") and (
        "no transcript" in normalized
        or "real stt provider required" in normalized
        or "no speech detected" in normalized
        or "not clear enough" in normalized
    ):
        return True
    return False