"""Speech-to-text helpers for desktop interview mode."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Protocol
import wave

from .audio_handler import AudioCapture
from .config_manager import ModelConfig

try:
    import whisper  # type: ignore[import-not-found]

    WHISPER_RUNTIME_AVAILABLE = True
except ImportError:
    whisper = None
    WHISPER_RUNTIME_AVAILABLE = False

try:
    import speech_recognition as sr  # type: ignore[import-not-found]

    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    sr = None
    SPEECH_RECOGNITION_AVAILABLE = False


@dataclass
class TranscriptResult:
    transcript: str
    processing_seconds: float


class STTEngine(Protocol):
    def transcribe(self, audio_capture: AudioCapture) -> TranscriptResult:
        ...


class ScriptedSTTEngine:
    """A lightweight deterministic STT engine for orchestration and tests."""

    def transcribe(self, audio_capture: AudioCapture) -> TranscriptResult:
        transcript = audio_capture.transcript_hint.strip()
        if not transcript:
            transcript = "Audio captured. Real STT provider required."
        return TranscriptResult(transcript=transcript, processing_seconds=1.2)


class SpeechRecognitionSTTEngine:
    """Online speech-to-text using Google Speech API via the SpeechRecognition library."""

    def __init__(self, language: str = "en-US") -> None:
        if not SPEECH_RECOGNITION_AVAILABLE:
            raise RuntimeError(
                "SpeechRecognition is not installed in this app build. "
                "Rebuild the desktop installer after installing requirements.txt."
            )
        self.language = language
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.energy_threshold = 280

    def transcribe(self, audio_capture: AudioCapture) -> TranscriptResult:
        started = time.perf_counter()
        if not audio_capture.raw_audio.strip(b"\x00"):
            hint = audio_capture.transcript_hint.strip()
            transcript = hint or "Audio captured. No speech detected."
            return TranscriptResult(transcript=transcript, processing_seconds=round(time.perf_counter() - started, 3))

        wav_path = _write_temp_wav(audio_capture)
        try:
            with sr.AudioFile(str(wav_path)) as source:
                audio = self._recognizer.record(source)
            try:
                transcript = self._recognizer.recognize_google(audio, language=self.language)
            except sr.UnknownValueError:
                transcript = ""
            except sr.RequestError as error:
                raise RuntimeError(
                    "Speech-to-text service is unreachable. Check the PC internet connection and try Listen again."
                ) from error
        finally:
            wav_path.unlink(missing_ok=True)

        transcript = (transcript or "").strip()
        if not transcript:
            transcript = "Audio captured. Speech was not clear enough to transcribe."
        return TranscriptResult(
            transcript=transcript,
            processing_seconds=round(time.perf_counter() - started, 3),
        )


class WhisperSTTEngine:
    """Optional local whisper-backed STT engine."""

    def __init__(self, model_name: str = "whisper-tiny") -> None:
        if not WHISPER_RUNTIME_AVAILABLE:
            raise RuntimeError("whisper runtime is not installed.")

        normalized_name = model_name.replace("whisper-", "", 1)
        self.model_name = model_name
        self._normalized_name = normalized_name
        self._model = None  # lazy-loaded on first transcribe to avoid blocking session creation

    def _ensure_model_loaded(self) -> None:
        if self._model is None:
            self._model = whisper.load_model(self._normalized_name)

    def transcribe(self, audio_capture: AudioCapture) -> TranscriptResult:
        self._ensure_model_loaded()
        started = time.perf_counter()
        _ensure_ffmpeg_on_path()
        wav_path = _write_temp_wav(audio_capture)
        try:
            result = self._model.transcribe(str(wav_path), fp16=False)
        finally:
            wav_path.unlink(missing_ok=True)

        transcript = (result.get("text") or "").strip()
        if not transcript:
            transcript = audio_capture.transcript_hint.strip() or "Audio captured. Whisper returned no transcript."
        return TranscriptResult(
            transcript=transcript,
            processing_seconds=round(time.perf_counter() - started, 3),
        )


def build_stt_engine(model_config: ModelConfig, language: str | None = None) -> STTEngine:
    normalized = model_config.stt_model.strip().lower()
    listen_language = (language or "en-US").strip() or "en-US"

    if normalized in {"speech_recognition", "google", "auto", "live"}:
        if SPEECH_RECOGNITION_AVAILABLE:
            return SpeechRecognitionSTTEngine(language=listen_language)
        if WHISPER_RUNTIME_AVAILABLE:
            return WhisperSTTEngine("whisper-tiny")
        raise RuntimeError(_missing_stt_runtime_message())

    if normalized.startswith("whisper"):
        if WHISPER_RUNTIME_AVAILABLE:
            return WhisperSTTEngine(model_config.stt_model)
        if SPEECH_RECOGNITION_AVAILABLE:
            return SpeechRecognitionSTTEngine(language=listen_language)
        raise RuntimeError(_missing_stt_runtime_message())

    if normalized == "scripted":
        if SPEECH_RECOGNITION_AVAILABLE and microphone_runtime_available_for_stt():
            return SpeechRecognitionSTTEngine(language=listen_language)
        if model_config.offline_fallback_enabled:
            return ScriptedSTTEngine()
        raise ValueError(f"Unsupported STT model: {model_config.stt_model}")

    if SPEECH_RECOGNITION_AVAILABLE:
        return SpeechRecognitionSTTEngine(language=listen_language)
    if model_config.offline_fallback_enabled:
        return ScriptedSTTEngine()

    raise ValueError(f"Unsupported STT model: {model_config.stt_model}")


def _missing_stt_runtime_message() -> str:
    return (
        "Speech-to-text is not available in this app build. "
        "Rebuild Career Copilot Premium with SpeechRecognition installed, "
        "then reinstall the desktop app."
    )


def stt_runtime_status() -> dict[str, object]:
    """Diagnostics for overlay/dashboard status bars."""
    if SPEECH_RECOGNITION_AVAILABLE:
        return {
            "ready": True,
            "engine": "google_speech",
            "label": "STT: Google Speech Ready",
            "message": "Listen will transcribe interviewer speech using Google Speech (internet required).",
        }
    if WHISPER_RUNTIME_AVAILABLE:
        return {
            "ready": True,
            "engine": "whisper",
            "label": "STT: Whisper Ready",
            "message": "Listen will transcribe interviewer speech locally with Whisper.",
        }
    return {
        "ready": False,
        "engine": "missing",
        "label": "STT: Not installed — rebuild app",
        "message": _missing_stt_runtime_message(),
    }


def microphone_runtime_available_for_stt() -> bool:
    from .audio_handler import microphone_capture_status

    status = microphone_capture_status()
    return bool(status.get("can_capture", False))


def speech_recognition_runtime_available() -> bool:
    return SPEECH_RECOGNITION_AVAILABLE


def whisper_runtime_available() -> bool:
    return WHISPER_RUNTIME_AVAILABLE


def resolve_ffmpeg_executable() -> Path | None:
    discovered = shutil.which("ffmpeg")
    if discovered:
        return Path(discovered)

    local_app_data = Path(os.environ.get("LOCALAPPDATA", "")) if os.environ.get("LOCALAPPDATA") else None
    candidates: list[Path] = []
    if local_app_data is not None:
        candidates.extend(
            [
                local_app_data / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
                local_app_data / "Microsoft" / "WindowsApps" / "ffmpeg.exe",
            ]
        )
        package_root = local_app_data / "Microsoft" / "WinGet" / "Packages"
        if package_root.exists():
            candidates.extend(package_root.glob("**/ffmpeg.exe"))

    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.extend(
            [
                Path(program_files) / "ffmpeg" / "bin" / "ffmpeg.exe",
                Path(program_files) / "FFmpeg" / "bin" / "ffmpeg.exe",
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _ensure_ffmpeg_on_path() -> Path | None:
    executable = resolve_ffmpeg_executable()
    if executable is None:
        return None

    ffmpeg_directory = str(executable.parent)
    path_value = os.environ.get("PATH", "")
    path_entries = path_value.split(os.pathsep) if path_value else []
    normalized_entries = {entry.lower() for entry in path_entries}
    if ffmpeg_directory.lower() not in normalized_entries:
        os.environ["PATH"] = os.pathsep.join([ffmpeg_directory, *path_entries]) if path_entries else ffmpeg_directory
    return executable


def default_stt_temp_directory() -> Path:
    from runtime_paths import cache_root

    directory = cache_root() / "stt_temp"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write_temp_wav(audio_capture: AudioCapture) -> Path:
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
        dir=default_stt_temp_directory(),
    )
    temp_file.close()
    wav_path = Path(temp_file.name)

    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(audio_capture.channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(audio_capture.sample_rate)
        wav_file.writeframes(audio_capture.raw_audio)

    return wav_path