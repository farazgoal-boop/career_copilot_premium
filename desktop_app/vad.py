"""Lightweight voice activity and auto-stop heuristics for desktop interview mode."""

from __future__ import annotations

from dataclasses import dataclass

from .audio_handler import AudioCapture

DEFAULT_MAX_RECORD_SECONDS = 8.0
MIN_ACTIVE_AMPLITUDE = 80.0


@dataclass
class VoiceActivityDecision:
    speech_detected: bool
    should_auto_stop: bool
    reason: str
    average_amplitude: float


def analyze_audio_capture(
    audio_capture: AudioCapture,
    max_record_seconds: float = DEFAULT_MAX_RECORD_SECONDS,
) -> VoiceActivityDecision:
    average_amplitude = _estimate_average_amplitude(audio_capture.raw_audio)
    speech_detected = bool(audio_capture.transcript_hint.strip()) or average_amplitude >= MIN_ACTIVE_AMPLITUDE

    if audio_capture.duration_seconds >= max_record_seconds:
        return VoiceActivityDecision(
            speech_detected=speech_detected,
            should_auto_stop=True,
            reason="max_duration_reached",
            average_amplitude=average_amplitude,
        )

    if speech_detected and average_amplitude < MIN_ACTIVE_AMPLITUDE / 2:
        return VoiceActivityDecision(
            speech_detected=True,
            should_auto_stop=True,
            reason="speech_tail_detected",
            average_amplitude=average_amplitude,
        )

    return VoiceActivityDecision(
        speech_detected=speech_detected,
        should_auto_stop=False,
        reason="continue_recording",
        average_amplitude=average_amplitude,
    )


def _estimate_average_amplitude(raw_audio: bytes) -> float:
    if len(raw_audio) < 2:
        return 0.0

    sample_count = len(raw_audio) // 2
    if sample_count == 0:
        return 0.0

    total = 0
    for index in range(0, sample_count * 2, 2):
        sample = int.from_bytes(raw_audio[index : index + 2], byteorder="little", signed=True)
        total += abs(sample)
    return total / sample_count