"""Shared contract models for the mobile overlay and bubble runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class MobileBridgeAction:
    action_id: str
    label: str
    session_command: str
    fallback_action: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "MobileBridgeAction":
        return cls(
            action_id=str(payload.get("action_id", "")),
            label=str(payload.get("label", "")),
            session_command=str(payload.get("session_command", "")),
            fallback_action=str(payload.get("fallback_action", "") or "") or None,
        )


@dataclass(frozen=True)
class MobileBubbleState:
    status: str
    visible: bool
    headline: str
    body: str
    confidence_score: int = 0
    provider_status: str = ""
    alternatives: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "MobileBubbleState":
        return cls(
            status=str(payload.get("status", "idle")),
            visible=bool(payload.get("visible", False)),
            headline=str(payload.get("headline", "")),
            body=str(payload.get("body", "")),
            confidence_score=int(payload.get("confidence_score", 0) or 0),
            provider_status=str(payload.get("provider_status", "") or ""),
            alternatives=[str(item) for item in payload.get("alternatives", []) or []],
        )


@dataclass(frozen=True)
class MobileBridgeSnapshot:
    source_version: str
    session_id: str
    profile_name: str
    company_name: str
    role_title: str
    meeting_source: str
    meeting_capture_mode: str
    meeting_window_name: str
    camera_layout_preference: str
    worker_status: str
    turn_count: int
    session_armed: bool
    microphone_enabled: bool
    persistent_prompt: str
    live_prompt: str
    notifications: list[dict[str, str]]
    command_queue_path: str
    session_database_path: str
    bubble: MobileBubbleState
    actions: list[MobileBridgeAction]
    required_permissions: list[str]
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "MobileBridgeSnapshot":
        bubble_payload = payload.get("bubble", {})
        return cls(
            source_version=str(payload.get("source_version", "")),
            session_id=str(payload.get("session_id", "")),
            profile_name=str(payload.get("profile_name", "")),
            company_name=str(payload.get("company_name", "")),
            role_title=str(payload.get("role_title", "")),
            meeting_source=str(payload.get("meeting_source", "Manual / generic interview") or "Manual / generic interview"),
            meeting_capture_mode=str(payload.get("meeting_capture_mode", "Companion workspace with live mic capture") or "Companion workspace with live mic capture"),
            meeting_window_name=str(payload.get("meeting_window_name", "") or ""),
            camera_layout_preference=str(payload.get("camera_layout_preference", "Keep Career Copilot beside the meeting window") or "Keep Career Copilot beside the meeting window"),
            worker_status=str(payload.get("worker_status", "")),
            turn_count=int(payload.get("turn_count", 0) or 0),
            session_armed=bool(payload.get("session_armed", False)),
            microphone_enabled=bool(payload.get("microphone_enabled", False)),
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
            command_queue_path=str(payload.get("command_queue_path", "")),
            session_database_path=str(payload.get("session_database_path", "")),
            bubble=MobileBubbleState.from_dict(dict(bubble_payload) if isinstance(bubble_payload, dict) else {}),
            actions=[MobileBridgeAction.from_dict(dict(item)) for item in payload.get("actions", []) if isinstance(item, dict)],
            required_permissions=[str(item) for item in payload.get("required_permissions", []) or []],
            updated_at=str(payload.get("updated_at", "")),
        )