"""Build mobile bubble snapshots from the saved desktop session state."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

from desktop_app.runtime_controller import enqueue_session_command, find_session_registry_entry, load_registered_session_state
from desktop_app.utils import sanitize_display_text

from .contracts import MobileBridgeAction, MobileBridgeSnapshot, MobileBubbleState

MOBILE_BRIDGE_SOURCE_VERSION = "desktop_session_store_v1"
MOBILE_REQUIRED_PERMISSIONS = [
    "SYSTEM_ALERT_WINDOW",
    "FOREGROUND_SERVICE",
    "POST_NOTIFICATIONS",
    "RECORD_AUDIO",
]


def build_mobile_bridge_snapshot(payload: dict[str, object], entry: dict[str, object]) -> MobileBridgeSnapshot:
    bubble = MobileBubbleState(
        status=str(payload.get("overlay_status", "idle")),
        visible=bool(payload.get("overlay_visible", False)),
        headline=_build_bubble_headline(payload),
        body=_build_bubble_body(payload),
        confidence_score=int(payload.get("confidence_score", 0) or 0),
        provider_status=str(payload.get("provider_status", "") or ""),
        alternatives=[str(item) for item in payload.get("alternatives", []) or []],
    )
    return MobileBridgeSnapshot(
        source_version=MOBILE_BRIDGE_SOURCE_VERSION,
        session_id=str(entry.get("session_id", "")),
        profile_name=str(entry.get("profile_name", "")),
        company_name=str(entry.get("company_name", "")),
        role_title=str(entry.get("role_title", "")),
        meeting_source=str(payload.get("meeting_source", "Manual / generic interview") or "Manual / generic interview"),
        meeting_capture_mode=str(payload.get("meeting_capture_mode", "Companion workspace with live mic capture") or "Companion workspace with live mic capture"),
        meeting_window_name=str(payload.get("meeting_window_name", "") or ""),
        camera_layout_preference=str(payload.get("camera_layout_preference", "Keep Career Copilot beside the meeting window") or "Keep Career Copilot beside the meeting window"),
        worker_status=str(entry.get("worker_status", "stopped") or "stopped"),
        turn_count=int(payload.get("turn_count", 0) or 0),
        session_armed=bool(payload.get("session_armed", False)),
        microphone_enabled=bool(payload.get("microphone_enabled", entry.get("microphone_enabled", False))),
        persistent_prompt=str(payload.get("persistent_prompt", "") or ""),
        live_prompt=str(payload.get("live_prompt", "") or ""),
        notifications=[
            {
                "level": str(item.get("level", "info") or "info"),
                "title": str(item.get("title", "") or ""),
                "message": str(item.get("message", "") or ""),
                "created_at": str(item.get("created_at", "") or ""),
            }
            for item in payload.get("notifications", [])
            if isinstance(item, dict)
        ],
        command_queue_path=str(entry.get("session_command_queue_path", "")),
        session_database_path=str(entry.get("session_database_path", "")),
        bubble=bubble,
        actions=_build_mobile_actions(payload),
        required_permissions=list(MOBILE_REQUIRED_PERMISSIONS),
        updated_at=str(payload.get("updated_at", "")),
    )


def build_mobile_bridge_snapshot_for_session(
    session_id: str,
    registry_path: str | Path | None = None,
) -> MobileBridgeSnapshot:
    entry = find_session_registry_entry(session_id, registry_path)
    payload = load_registered_session_state(session_id, registry_path)
    return build_mobile_bridge_snapshot(payload, entry)


def export_mobile_bridge_snapshot(
    session_id: str,
    destination: str | Path,
    registry_path: str | Path | None = None,
) -> Path:
    snapshot = build_mobile_bridge_snapshot_for_session(session_id, registry_path)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    return path


def load_mobile_bridge_snapshot(path: str | Path) -> MobileBridgeSnapshot:
    source = str(path)
    if source.startswith("http://") or source.startswith("https://"):
        payload = json.loads(urlopen(source).read().decode("utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("snapshot"), dict):
            payload = payload["snapshot"]
    else:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Mobile bridge snapshot must be a JSON object.")
    return MobileBridgeSnapshot.from_dict(payload)


def enqueue_mobile_bridge_action(
    snapshot: MobileBridgeSnapshot,
    action_id: str,
    registry_path: str | Path | None = None,
) -> Path:
    action = next((item for item in snapshot.actions if item.action_id == action_id), None)
    if action is None:
        raise ValueError(f"Unknown mobile action: {action_id}")

    return enqueue_session_command(
        snapshot.session_id,
        action.session_command,
        registry_path=registry_path,
        fallback_action=action.fallback_action,
    )


def _build_mobile_actions(payload: dict[str, object]) -> list[MobileBridgeAction]:
    actions = [
        MobileBridgeAction(action_id="listen", label="Listen (F2)", session_command="listen"),
        MobileBridgeAction(action_id="toggle", label="Toggle Mic", session_command="toggle"),
        MobileBridgeAction(action_id="status", label="Refresh Status", session_command="status"),
        MobileBridgeAction(action_id="stop_worker", label="Stop Worker", session_command="stop-worker"),
    ]
    if int(payload.get("turn_count", 0) or 0) > 0:
        actions.extend(
            [
                MobileBridgeAction(
                    action_id="fallback_simple",
                    label="Simple",
                    session_command="fallback",
                    fallback_action="simple",
                ),
                MobileBridgeAction(
                    action_id="fallback_alternatives",
                    label="Alt",
                    session_command="fallback",
                    fallback_action="alternatives",
                ),
                MobileBridgeAction(
                    action_id="fallback_emergency",
                    label="Emergency",
                    session_command="fallback",
                    fallback_action="emergency",
                ),
            ]
        )
    return actions


def _is_stt_failure_text(text: str) -> bool:
    normalized = str(text or "").strip().casefold()
    if not normalized:
        return True
    return normalized in {
        "audio captured. real stt provider required.",
        "audio captured. whisper returned no transcript.",
    } or normalized.startswith("audio captured.")


def _build_bubble_headline(payload: dict[str, object]) -> str:
    status = str(payload.get("overlay_status", "idle"))
    if status == "answer_ready":
        raw_transcript = str(
            payload.get("transcript", "") or payload.get("last_transcript", "")
        )
        if _is_stt_failure_text(raw_transcript):
            return "Desktop could not hear the question"
        transcript = sanitize_display_text(raw_transcript, fallback="")
        return transcript or "Suggested answer ready"
    if status == "listening":
        return "Listening for the interviewer"
    if bool(payload.get("session_armed", False)):
        return "Session armed"
    return "Waiting for the next interviewer prompt."


def _build_bubble_body(payload: dict[str, object]) -> str:
    status = str(payload.get("overlay_status", "idle"))
    if status == "answer_ready":
        raw_transcript = str(
            payload.get("transcript", "") or payload.get("last_transcript", "")
        )
        if _is_stt_failure_text(raw_transcript):
            return (
                "Listen uses your PC microphone (not the phone). "
                "On the desktop: enable mic or Stereo Mix, then press Listen (F2) again."
            )
        suggested_answer = sanitize_display_text(
            payload.get("suggested_answer", "") or payload.get("last_answer", ""),
            fallback="",
        )
        provider = str(payload.get("provider_status", "") or "").strip()
        if suggested_answer and provider:
            return f"{suggested_answer}\n\n— {provider}"
        return suggested_answer or "Answer suggestion unavailable."
    if status == "listening":
        return "Desktop is capturing call audio now. Keep PC and phone on the same Wi-Fi."
    if bool(payload.get("session_armed", False)):
        return "Use the bubble actions to start or control the live session."
    return "Open the desktop runtime or session worker to activate mobile controls."