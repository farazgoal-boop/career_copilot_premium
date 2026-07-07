"""Session audio recording storage: one continuous .webm file per session.

Unlike the Visual Context Library (profile-scoped, persists across sessions),
a recording belongs to exactly one call -- storage is keyed by session_id
under the cache root, not under the candidate's profile directory.
"""

from __future__ import annotations

from datetime import datetime, timezone

from runtime_paths import session_recording_path

ALLOWED_MIME_TYPE = "audio/webm"
MAX_RECORDING_BYTES = 250 * 1024 * 1024  # generous cap for multi-hour calls at modest bitrate


class RecordingValidationError(ValueError):
    """Raised when an uploaded recording fails validation."""


def validate_recording_upload(size_bytes: int) -> None:
    if size_bytes <= 0:
        raise RecordingValidationError("Recording is empty.")
    if size_bytes > MAX_RECORDING_BYTES:
        raise RecordingValidationError(
            f"Recording is too large ({size_bytes / 1_048_576:.1f} MB). "
            f"Max size is {MAX_RECORDING_BYTES // 1_048_576} MB."
        )


def save_session_recording(session_id: str, file_bytes: bytes) -> dict[str, object]:
    """Validate and persist a session's recording. Returns metadata for session state."""
    validate_recording_upload(len(file_bytes))

    path = session_recording_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_bytes)

    return {
        "recording_path": str(path),
        "recording_mime_type": ALLOWED_MIME_TYPE,
        "recording_size_bytes": len(file_bytes),
        "recording_saved_at": _utc_now_iso(),
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
