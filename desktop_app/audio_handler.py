"""Audio capture abstractions for desktop interview mode."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Callable, Protocol
import wave

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    sd = None
    SOUNDDEVICE_AVAILABLE = False

_MIC_STATUS_CACHE: dict[str, object] = {"at": 0.0, "payload": None}
_MIC_STATUS_TTL_SECONDS = 45.0
_DEVICE_LIST_CACHE: dict[str, object] = {"at": 0.0, "devices": None}
_DEVICE_LIST_TTL_SECONDS = 45.0


@dataclass
class AudioCapture:
    raw_audio: bytes
    started_at: str
    stopped_at: str
    duration_seconds: float
    transcript_hint: str = ""
    sample_rate: int = 16000
    channels: int = 1
    source: str = "unknown"


class AudioRecorder(Protocol):
    @property
    def is_recording(self) -> bool:
        ...

    def start_recording(self) -> None:
        ...

    def stop_recording(self) -> AudioCapture:
        ...


class ScriptedAudioRecorder:
    """Deterministic recorder used by tests and early orchestration flows."""

    def __init__(self, scripted_transcript: str = "") -> None:
        self.scripted_transcript = scripted_transcript
        self._recording = False
        self._started_at: str | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        self._recording = True
        self._started_at = _utc_now_iso()

    def stop_recording(self) -> AudioCapture:
        if not self._recording:
            raise RuntimeError("Recording has not started.")

        self._recording = False
        stopped_at = _utc_now_iso()
        return AudioCapture(
            raw_audio=self.scripted_transcript.encode("utf-8"),
            started_at=self._started_at or stopped_at,
            stopped_at=stopped_at,
            duration_seconds=2.0,
            transcript_hint=self.scripted_transcript,
            source="scripted",
        )


class WavAudioRecorder:
    """Reads a WAV file as captured audio for deterministic local testing."""

    def __init__(self, wav_path: str | Path, transcript_hint: str = "") -> None:
        self.wav_path = Path(wav_path)
        self.transcript_hint = transcript_hint
        self._recording = False
        self._started_at: str | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        self._recording = True
        self._started_at = _utc_now_iso()

    def stop_recording(self) -> AudioCapture:
        if not self._recording:
            raise RuntimeError("Recording has not started.")

        self._recording = False
        with wave.open(str(self.wav_path), "rb") as wav_file:
            raw_audio = wav_file.readframes(wav_file.getnframes())
            duration_seconds = wav_file.getnframes() / float(wav_file.getframerate())
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()

        stopped_at = _utc_now_iso()
        return AudioCapture(
            raw_audio=raw_audio,
            started_at=self._started_at or stopped_at,
            stopped_at=stopped_at,
            duration_seconds=duration_seconds,
            transcript_hint=self.transcript_hint,
            sample_rate=sample_rate,
            channels=channels,
            source="wav_file",
        )


STEREO_MIX_KEYWORDS = (
    "stereo mix",
    "loopback",
    "what u hear",
    "wave out",
)
VIRTUAL_CABLE_KEYWORDS = (
    "vb-cable",
    "vb cable",
    "cable output",
    "cable-a",
    "blackhole",
    "pulseaudio monitor",
    "monitor of",
)
CALL_AUDIO_KEYWORDS = STEREO_MIX_KEYWORDS + VIRTUAL_CABLE_KEYWORDS + ("speakers",)


class MicrophoneAudioRecorder:
    """Real microphone or call-audio recorder backed by sounddevice."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        max_record_seconds: float = 12.0,
        device_index: int | None = None,
        source_label: str = "microphone",
    ) -> None:
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("sounddevice is required for real microphone capture.")

        self.sample_rate = sample_rate
        self.channels = channels
        self.max_record_seconds = max_record_seconds
        self.device_index = device_index
        self.source_label = source_label
        self._recording = False
        self._started_at: str | None = None
        self._frames: list[bytes] = []
        self._stream = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        if self._recording:
            return

        if self.device_index is None and not _input_device_names():
            raise RuntimeError(
                "No input microphone device is available. Windows is not exposing a recording endpoint."
            )

        self._frames = []
        self._started_at = _utc_now_iso()

        def callback(indata, frames, time_info, status) -> None:  # type: ignore[no-untyped-def]
            del frames, time_info
            if status:
                return
            self._frames.append(indata.copy().tobytes())

        stream_kwargs: dict[str, object] = {
            "samplerate": self.sample_rate,
            "channels": self.channels,
            "dtype": "int16",
            "callback": callback,
            "blocksize": 0,
        }
        if self.device_index is not None:
            stream_kwargs["device"] = self.device_index

        try:
            self._stream = sd.InputStream(**stream_kwargs)
            self._stream.start()
        except Exception as error:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            raise RuntimeError(
                "Microphone capture could not start. Check that Windows has an active recording device and microphone permission."
            ) from error
        self._recording = True

    def stop_recording(self) -> AudioCapture:
        if not self._recording:
            raise RuntimeError("Recording has not started.")

        self._recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        stopped_at = _utc_now_iso()
        duration_seconds = min(_duration_from_timestamps(self._started_at, stopped_at), self.max_record_seconds)
        return AudioCapture(
            raw_audio=b"".join(self._frames),
            started_at=self._started_at or stopped_at,
            stopped_at=stopped_at,
            duration_seconds=duration_seconds,
            sample_rate=self.sample_rate,
            channels=self.channels,
            source=self.source_label,
        )


class CallAudioRecorder(MicrophoneAudioRecorder):
    """Captures Zoom/WhatsApp call audio via Stereo Mix, loopback, or microphone fallback."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, max_record_seconds: float = 12.0) -> None:
        device_index, source_label = resolve_call_audio_device()
        super().__init__(
            sample_rate=sample_rate,
            channels=channels,
            max_record_seconds=max_record_seconds,
            device_index=device_index,
            source_label=source_label,
        )


def _match_device_keyword(name: str, keywords: tuple[str, ...]) -> bool:
    lowered = name.casefold()
    return any(keyword in lowered for keyword in keywords)


def _query_devices_cached(*, force_refresh: bool = False) -> list[object] | None:
    if not SOUNDDEVICE_AVAILABLE or sd is None:
        return None
    age = time.time() - float(_DEVICE_LIST_CACHE.get("at", 0.0))
    cached = _DEVICE_LIST_CACHE.get("devices")
    if not force_refresh and cached is not None and age < _DEVICE_LIST_TTL_SECONDS:
        return list(cached)  # type: ignore[arg-type]
    try:
        devices = list(sd.query_devices())
    except Exception:
        return None
    _DEVICE_LIST_CACHE["at"] = time.time()
    _DEVICE_LIST_CACHE["devices"] = devices
    return devices


def resolve_call_audio_device(*, force_refresh: bool = False) -> tuple[int | None, str]:
    """Pick the best input: Stereo Mix -> VB-Cable/BlackHole/Pulse -> microphone."""
    if not SOUNDDEVICE_AVAILABLE:
        return None, "microphone"

    devices = _query_devices_cached(force_refresh=force_refresh)
    if devices is None:
        return None, "microphone"

    stereo_candidates: list[tuple[int, str]] = []
    cable_candidates: list[tuple[int, str]] = []
    default_input: tuple[int, str] | None = None

    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0) or 0) <= 0:
            continue
        name = str(device.get("name", "")).strip()
        lowered = name.casefold()
        if default_input is None:
            default_input = (index, name)
        if _match_device_keyword(lowered, STEREO_MIX_KEYWORDS):
            stereo_candidates.append((index, name))
        elif _match_device_keyword(lowered, VIRTUAL_CABLE_KEYWORDS):
            cable_candidates.append((index, name))

    if stereo_candidates:
        chosen_index, chosen_name = stereo_candidates[0]
        return chosen_index, f"stereo_mix:{chosen_name}"
    if cable_candidates:
        chosen_index, chosen_name = cable_candidates[0]
        return chosen_index, f"virtual_cable:{chosen_name}"
    if default_input is not None:
        return default_input[0], f"microphone:{default_input[1]}"

    return None, "microphone"


def record_until_silence(
    max_seconds: float = 12.0,
    silence_seconds: float = 1.4,
    min_speech_seconds: float = 0.6,
    silence_amplitude: float = 120.0,
    prefer_call_audio: bool = True,
) -> AudioCapture:
    """Record live audio until the interviewer stops speaking."""
    if not SOUNDDEVICE_AVAILABLE:
        raise RuntimeError("sounddevice is required for live call listening.")

    recorder = CallAudioRecorder(max_record_seconds=max_seconds) if prefer_call_audio else MicrophoneAudioRecorder(
        max_record_seconds=max_seconds
    )
    recorder.start_recording()
    started = time.perf_counter()
    speech_started_at: float | None = None
    last_active_at = started

    try:
        while True:
            time.sleep(0.15)
            elapsed = time.perf_counter() - started
            if elapsed >= max_seconds:
                break

            if not recorder._frames:
                continue

            recent_chunk = recorder._frames[-1]
            amplitude = _estimate_chunk_amplitude(recent_chunk)
            if amplitude >= silence_amplitude:
                if speech_started_at is None:
                    speech_started_at = time.perf_counter()
                last_active_at = time.perf_counter()
                continue

            if speech_started_at is not None:
                quiet_for = time.perf_counter() - last_active_at
                speech_duration = last_active_at - speech_started_at
                if quiet_for >= silence_seconds and speech_duration >= min_speech_seconds:
                    break
    finally:
        return recorder.stop_recording()


def start_continuous_listen(
    on_capture_ready: Callable[[AudioCapture], None],
    max_seconds: float = 12.0,
    prefer_call_audio: bool = True,
) -> threading.Thread:
    """Run live listen in a background thread and invoke callback with captured audio."""

    def worker() -> None:
        try:
            capture = record_until_silence(max_seconds=max_seconds, prefer_call_audio=prefer_call_audio)
            on_capture_ready(capture)
        except Exception:
            return

    thread = threading.Thread(target=worker, name="career-copilot-live-listen", daemon=True)
    thread.start()
    return thread


def microphone_runtime_available() -> bool:
    return SOUNDDEVICE_AVAILABLE


def microphone_capture_status(*, force_refresh: bool = False) -> dict[str, object]:
    age = time.time() - float(_MIC_STATUS_CACHE.get("at", 0.0))
    cached_payload = _MIC_STATUS_CACHE.get("payload")
    if not force_refresh and isinstance(cached_payload, dict) and age < _MIC_STATUS_TTL_SECONDS:
        return dict(cached_payload)

    runtime_available = microphone_runtime_available()
    input_devices = _input_device_names(force_refresh=force_refresh)
    input_available = bool(input_devices)
    call_device_index, call_source = resolve_call_audio_device(force_refresh=force_refresh)
    call_audio_ready = runtime_available and input_available
    using_loopback = call_source.startswith(("call_audio:", "stereo_mix:", "virtual_cable:"))
    device_kind = call_source.split(":", 1)[0] if ":" in call_source else "microphone"
    overlay_label = audio_status_label(call_source)

    if not runtime_available:
        message = "Live microphone capture is unavailable because the sounddevice runtime is not installed."
    elif not input_available:
        message = "Windows is not exposing a recording endpoint, so live microphone capture is unavailable."
    elif device_kind == "stereo_mix":
        message = f"Stereo Mix capture ready via {call_source.split(':', 1)[1]}."
    elif device_kind == "virtual_cable":
        message = f"Virtual cable capture ready via {call_source.split(':', 1)[1]}."
    else:
        message = (
            "Microphone capture is available. For Zoom/WhatsApp call audio, enable Stereo Mix "
            "or install VB-Cable (vb-audio.com/Cable)."
        )

    payload = {
        "runtime_available": runtime_available,
        "input_available": input_available,
        "can_capture": runtime_available and input_available,
        "call_audio_ready": call_audio_ready,
        "call_audio_source": call_source,
        "call_audio_device_index": call_device_index,
        "using_loopback": using_loopback,
        "device_kind": device_kind,
        "overlay_audio_label": overlay_label,
        "input_devices": input_devices,
        "message": message,
    }
    _MIC_STATUS_CACHE["at"] = time.time()
    _MIC_STATUS_CACHE["payload"] = payload
    return dict(payload)


def audio_status_label(call_source: str | None = None) -> str:
    """Human-readable audio status for overlay status bar."""
    if not SOUNDDEVICE_AVAILABLE:
        return "No Audio Device"
    _, source = resolve_call_audio_device() if call_source is None else (None, call_source)
    kind = source.split(":", 1)[0] if ":" in source else "microphone"
    if kind == "stereo_mix":
        return "Speaker Capture (Stereo Mix)"
    if kind == "virtual_cable":
        return "Speaker Capture (VB-Cable)"
    if kind == "microphone" and source != "microphone":
        return "Microphone Ready"
    if kind == "microphone":
        status = microphone_capture_status()
        if status.get("can_capture"):
            return "Microphone Ready"
        return "No Audio Device"
    return "Microphone Ready"


def _input_device_names(*, force_refresh: bool = False) -> list[str]:
    if not SOUNDDEVICE_AVAILABLE:
        return []

    devices = _query_devices_cached(force_refresh=force_refresh)
    if devices is None:
        return []

    return [
        str(device.get("name", ""))
        for device in devices
        if int(device.get("max_input_channels", 0) or 0) > 0
    ]


def _duration_from_timestamps(started_at: str | None, stopped_at: str) -> float:
    if not started_at:
        return 0.0
    started = datetime.fromisoformat(started_at)
    stopped = datetime.fromisoformat(stopped_at)
    return max(0.0, (stopped - started).total_seconds())


def _estimate_chunk_amplitude(raw_audio: bytes) -> float:
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()