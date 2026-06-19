"""Desktop runtime assembly and session launch orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import TYPE_CHECKING

from .audio_handler import (
    AudioCapture,
    AudioRecorder,
    CallAudioRecorder,
    MicrophoneAudioRecorder,
    ScriptedAudioRecorder,
    microphone_capture_status,
    microphone_runtime_available,
)
from .database import delete_session, get_session_entry, get_session_state, get_session_state_by_path, list_session_entries, upsert_session_entry, upsert_session_state
from .encryption import read_encrypted_json_file, write_encrypted_json_file
from .hotkeys import HotkeyManager
from .interview_mode import DesktopInterviewMode
from .notifications import DesktopNotificationCenter
from .onboarding import PROFILE_FILENAME, CompleteUserProfile, is_session_ready, load_completed_profile
from .overlay import (
    LiveOverlayController,
    OverlayState,
    OverlayRuntime,
    build_listening_overlay,
    create_overlay_controller,
    create_overlay_runtime,
)
from .stt_engine import STTEngine
from .strategy_generator import StrategyPack, generate_strategy_pack, save_strategy_pack

if TYPE_CHECKING:
    from .main import DesktopRuntime

SESSION_STATE_FILENAME = "session_state.json"
SESSION_REGISTRY_FILENAME = "session_registry.json"
SESSION_COMMAND_QUEUE_FILENAME = "session_commands.json"
SESSION_DATABASE_FILENAME = "session_store.db"
SESSION_WORKER_STATE_FILENAME = "session_worker.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "session"


def default_session_registry_path() -> Path:
    from runtime_paths import session_registry_path

    return session_registry_path()


def default_session_database_path() -> Path:
    from runtime_paths import session_database_path

    return session_database_path()


def session_database_path_from_registry_path(path: str | Path | None = None) -> Path:
    if path is None:
        return default_session_database_path()
    registry_path = Path(path)
    return registry_path.parent / SESSION_DATABASE_FILENAME


def build_session_id(profile_name: str, company_name: str, role_title: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{_slugify(profile_name)}-{_slugify(company_name)}-{_slugify(role_title)}-{timestamp}"


@dataclass
class DesktopSessionController:
    runtime: DesktopRuntime
    profile_directory: Path
    profile: CompleteUserProfile
    strategy_pack: StrategyPack
    interview_mode: DesktopInterviewMode
    overlay_controller: LiveOverlayController
    notification_center: DesktopNotificationCenter = field(default_factory=DesktopNotificationCenter)
    session_armed: bool = False

    def arm_session(self, strategy_destination: str | Path | None = None) -> Path:
        destination = Path(strategy_destination) if strategy_destination else self.profile_directory / "strategy_pack.json"
        saved_path = save_strategy_pack(self.strategy_pack, destination)
        self.session_armed = True
        self.notification_center.info(
            "Session armed",
            f"Prepared strategy pack for {self.strategy_pack.company_brief.company_name} / {self.strategy_pack.company_brief.role_title}.",
        )
        return saved_path

    def toggle_recording(self) -> OverlayState:
        state = self.interview_mode.toggle_recording()
        if state.status == "listening":
            self.notification_center.info("Listening", "Microphone capture started for the next interviewer prompt.")
        elif state.status == "answer_ready":
            self.notification_center.info("Answer ready", state.suggested_answer[:140])
        return self.overlay_controller.update(state)

    def handle_auto_stop(self, audio_capture: AudioCapture) -> OverlayState:
        state = self.interview_mode.handle_auto_stop(audio_capture)
        if state.status == "listening":
            self.notification_center.info("Listening", "Voice activity continues; keeping the session armed.")
        elif state.status == "answer_ready":
            self.notification_center.info("Answer ready", state.suggested_answer[:140])
        return self.overlay_controller.update(state)

    def apply_fallback(self, action: str) -> OverlayState:
        state = self.interview_mode.apply_fallback(action)
        self.notification_center.warning(
            "Fallback applied",
            f"Switched the suggested answer using the '{action}' fallback flow.",
        )
        return self.overlay_controller.update(state)

    def hide_overlay(self) -> OverlayState:
        self.notification_center.info("Overlay hidden", "The overlay was hidden while the session remains active.")
        return self.overlay_controller.hide()

    def shutdown(self) -> None:
        self.notification_center.info("Session stopped", "Desktop interview controls and overlay resources were released.")
        self.overlay_controller.shutdown()
        self.interview_mode.shutdown()


@dataclass
class DesktopSessionRunner:
    controller: DesktopSessionController
    strategy_path: Path | None = None
    session_state_path: Path | None = None
    session_registry_path: Path | None = None
    session_command_queue_path: Path | None = None
    session_database_path: Path | None = None
    session_worker_state_path: Path | None = None
    prefer_microphone: bool = True
    session_id: str | None = None
    started: bool = False

    def start(self, strategy_destination: str | Path | None = None) -> Path:
        if self.session_id is None:
            self.session_id = build_session_id(
                self.controller.profile.identity.full_name,
                self.controller.strategy_pack.company_brief.company_name,
                self.controller.strategy_pack.company_brief.role_title,
            )
        self.strategy_path = self.controller.arm_session(strategy_destination)
        listening_state = build_listening_overlay(opacity=self.controller.interview_mode.overlay_opacity)
        self.controller.overlay_controller.update(listening_state)
        self.started = True
        self.save_session_state()
        return self.strategy_path

    def stop(self) -> None:
        self.started = False
        if self.session_id is not None:
            self.save_session_state()
        self.controller.shutdown()

    def toggle_recording(self) -> OverlayState:
        state = self.controller.toggle_recording()
        self.save_session_state()
        return state

    def handle_auto_stop(self, audio_capture: AudioCapture) -> OverlayState:
        state = self.controller.handle_auto_stop(audio_capture)
        self.save_session_state()
        return state

    def apply_fallback(self, action: str) -> OverlayState:
        state = self.controller.apply_fallback(action)
        self.save_session_state()
        return state

    def resolve_session_state_path(self, destination: str | Path | None = None) -> Path:
        if destination is not None:
            self.session_state_path = Path(destination)
        elif self.session_state_path is None:
            self.session_state_path = self.controller.profile_directory / SESSION_STATE_FILENAME
        return self.session_state_path

    def resolve_session_registry_path(self, destination: str | Path | None = None) -> Path:
        if destination is not None:
            self.session_registry_path = Path(destination)
        elif self.session_registry_path is None:
            self.session_registry_path = default_session_registry_path()
        return self.session_registry_path

    def resolve_session_command_queue_path(self, destination: str | Path | None = None) -> Path:
        if destination is not None:
            self.session_command_queue_path = Path(destination)
        elif self.session_command_queue_path is None:
            if self.session_id:
                self.session_command_queue_path = self.controller.profile_directory / f"{self.session_id}_{SESSION_COMMAND_QUEUE_FILENAME}"
            else:
                self.session_command_queue_path = self.controller.profile_directory / SESSION_COMMAND_QUEUE_FILENAME
        return self.session_command_queue_path

    def resolve_session_database_path(self, destination: str | Path | None = None) -> Path:
        if destination is not None:
            self.session_database_path = Path(destination)
        elif self.session_database_path is None:
            if self.session_registry_path is not None:
                self.session_database_path = session_database_path_from_registry_path(self.session_registry_path)
            else:
                self.session_database_path = default_session_database_path()
        return self.session_database_path

    def resolve_session_worker_state_path(self, destination: str | Path | None = None) -> Path:
        if destination is not None:
            self.session_worker_state_path = Path(destination)
        elif self.session_worker_state_path is None:
            if self.session_id:
                self.session_worker_state_path = self.controller.profile_directory / f"{self.session_id}_{SESSION_WORKER_STATE_FILENAME}"
            else:
                self.session_worker_state_path = self.controller.profile_directory / SESSION_WORKER_STATE_FILENAME
        return self.session_worker_state_path

    def build_diagnostics_payload(self) -> dict[str, object]:
        overlay_state = self.controller.interview_mode.overlay_state
        meeting_source = "Manual / generic interview"
        meeting_capture_mode = "Companion workspace with live mic capture"
        meeting_window_name = ""
        camera_layout_preference = "Keep Career Copilot beside the meeting window"
        if self.session_id is not None:
            persisted_state = get_session_state(self.resolve_session_database_path(), self.session_id) or {}
            meeting_source = str(persisted_state.get("meeting_source", meeting_source) or meeting_source)
            meeting_capture_mode = str(persisted_state.get("meeting_capture_mode", meeting_capture_mode) or meeting_capture_mode)
            meeting_window_name = str(persisted_state.get("meeting_window_name", meeting_window_name) or meeting_window_name)
            camera_layout_preference = str(
                persisted_state.get("camera_layout_preference", camera_layout_preference) or camera_layout_preference
            )
        return {
            "started": self.started,
            "session_armed": self.controller.session_armed,
            "microphone_enabled": self.prefer_microphone,
            "profile_name": self.controller.profile.identity.full_name,
            "session_id": self.session_id or "",
            "company_name": self.controller.strategy_pack.company_brief.company_name,
            "role_title": self.controller.strategy_pack.company_brief.role_title,
            "meeting_source": meeting_source,
            "meeting_capture_mode": meeting_capture_mode,
            "meeting_window_name": meeting_window_name,
            "camera_layout_preference": camera_layout_preference,
            "hotkey": self.controller.interview_mode.hotkey,
            "overlay_status": overlay_state.status,
            "overlay_visible": overlay_state.visible,
            "transcript": overlay_state.transcript,
            "suggested_answer": overlay_state.suggested_answer,
            "alternatives": list(overlay_state.alternatives),
            "notifications": [
                {
                    "level": event.level,
                    "title": event.title,
                    "message": event.message,
                    "created_at": event.created_at,
                }
                for event in self.controller.notification_center.recent(limit=12)
            ],
            "confidence_score": overlay_state.confidence_score,
            "provider_status": overlay_state.provider_status,
            "turn_count": len(self.controller.interview_mode.session_turns),
            "strategy_path": str(self.strategy_path) if self.strategy_path is not None else "",
            "session_state_path": str(self.session_state_path) if self.session_state_path is not None else "",
            "session_registry_path": str(self.session_registry_path) if self.session_registry_path is not None else "",
            "session_command_queue_path": str(self.session_command_queue_path) if self.session_command_queue_path is not None else "",
            "session_database_path": str(self.session_database_path) if self.session_database_path is not None else "",
            "session_worker_state_path": str(self.session_worker_state_path) if self.session_worker_state_path is not None else "",
            "updated_at": _utc_now_iso(),
        }

    def save_session_state(self, destination: str | Path | None = None) -> Path:
        path = self.resolve_session_state_path(destination)
        payload = self.build_diagnostics_payload()
        if self.session_id is not None:
            upsert_session_state(self.resolve_session_database_path(), self.session_id, payload)
        save_session_registry_entry(self)
        return path

    def load_saved_session_state(self) -> dict[str, object]:
        if self.session_id is not None:
            payload = get_session_state(self.resolve_session_database_path(), self.session_id)
            if payload is not None:
                return payload
        return load_session_state(self.resolve_session_state_path())

    def export_diagnostics(self, destination: str | Path) -> Path:
        path = Path(destination)
        return write_encrypted_json_file(path, self.build_diagnostics_payload())

    def build_status_report(self) -> str:
        diagnostics = self.build_diagnostics_payload()
        return (
            f"Session started: {diagnostics['started']}\n"
            f"Overlay status: {diagnostics['overlay_status']}\n"
            f"Overlay visible: {diagnostics['overlay_visible']}\n"
            f"Turns completed: {diagnostics['turn_count']}"
        )

    def build_startup_summary(self) -> str:
        if self.strategy_path is None:
            raise RuntimeError("Session runner has not been started yet.")
        summary = build_session_summary(self.controller, self.strategy_path)
        return summary + "\nSession state: started\n" + self.build_status_report()


def execute_runner_command(
    runner: DesktopSessionRunner,
    command: str,
    fallback_action: str | None = None,
    diagnostics_destination: str | Path | None = None,
) -> str:
    normalized_command = command.strip().lower()
    if normalized_command == "start":
        runner.start()
        return runner.build_startup_summary()

    if not runner.started:
        if normalized_command == "status":
            state_path = runner.resolve_session_state_path()
            try:
                return format_session_state_summary(load_session_state(state_path))
            except FileNotFoundError:
                pass
        runner.start()

    if normalized_command == "toggle":
        state = runner.toggle_recording()
        return _format_overlay_state(state)

    if normalized_command == "listen":
        from .live_listen import run_live_listen_cycle

        if runner.session_id is None:
            raise ValueError("Listen command requires an active session ID.")
        result = run_live_listen_cycle(runner.session_id, registry_path=runner.session_registry_path)
        runner.controller.overlay_controller.update(result.overlay_state)
        runner.save_session_state()
        return (
            f"Overlay status: {result.overlay_state.status}\n"
            f"Transcript: {result.transcript[:120]}\n"
            f"Provider status: {result.provider_status or 'n/a'}"
        )

    if normalized_command == "status":
        return runner.build_status_report()

    if normalized_command == "fallback":
        if not fallback_action:
            raise ValueError("Fallback command requires a fallback action.")
        try:
            state = runner.apply_fallback(fallback_action)
        except RuntimeError as error:
            raise ValueError("Fallback command requires an active interview turn before applying the action.") from error
        return _format_overlay_state(state)

    if normalized_command == "export-diagnostics":
        destination = Path(diagnostics_destination) if diagnostics_destination else runner.controller.profile_directory / "session_diagnostics.json"
        saved_path = runner.export_diagnostics(destination)
        return f"Diagnostics exported: {saved_path}"

    raise ValueError(f"Unsupported session command: {command}")


def execute_runner_script(runner: DesktopSessionRunner, commands: list[str]) -> list[str]:
    results: list[str] = []
    for raw_command in commands:
        command = raw_command.strip()
        if not command:
            continue

        fallback_action: str | None = None
        command_name = command
        if ":" in command:
            command_name, fallback_action = command.split(":", 1)
            command_name = command_name.strip()
            fallback_action = fallback_action.strip() or None

        results.append(
            execute_runner_command(
                runner,
                command_name,
                fallback_action=fallback_action,
            )
        )
    return results


def load_session_state(path: str | Path) -> dict[str, object]:
    state_path = Path(path)
    database_candidates = [state_path.parent / SESSION_DATABASE_FILENAME, default_session_database_path()]
    checked_paths: set[Path] = set()
    for database_path in database_candidates:
        if database_path in checked_paths:
            continue
        checked_paths.add(database_path)
        payload = get_session_state_by_path(database_path, state_path)
        if payload is not None:
            return payload
    raise FileNotFoundError(f"Session state not found for path: {state_path}")


def format_session_state_summary(payload: dict[str, object]) -> str:
    return (
        f"Session ID: {payload.get('session_id', '')}\n"
        f"Session started: {payload.get('started', False)}\n"
        f"Overlay status: {payload.get('overlay_status', 'unknown')}\n"
        f"Overlay visible: {payload.get('overlay_visible', False)}\n"
        f"Turns completed: {payload.get('turn_count', 0)}\n"
        f"Session state path: {payload.get('session_state_path', '')}"
    )


def load_session_registry(path: str | Path | None = None) -> dict[str, dict[str, object]]:
    registry_path = Path(path) if path is not None else default_session_registry_path()
    return list_session_entries(session_database_path_from_registry_path(registry_path))


def load_session_command_queue(path: str | Path) -> list[dict[str, object]]:
    queue_path = Path(path)
    if not queue_path.exists():
        return []
    return json.loads(queue_path.read_text(encoding="utf-8"))


def load_session_worker_state(path: str | Path) -> dict[str, object]:
    worker_state_path = Path(path)
    return json.loads(worker_state_path.read_text(encoding="utf-8"))


def save_session_worker_state(path: str | Path, payload: dict[str, object]) -> Path:
    worker_state_path = Path(path)
    worker_state_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomically(worker_state_path, payload)
    return worker_state_path


def save_session_command_queue(path: str | Path, commands: list[dict[str, object]]) -> Path:
    queue_path = Path(path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomically(queue_path, commands)
    return queue_path


def _write_json_atomically(path: Path, data: object) -> None:
    import os
    import tempfile
    import time
    text = json.dumps(data, indent=2, ensure_ascii=False)
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(text)
            except Exception:
                os.unlink(tmp)
                raise
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt < 2:
                time.sleep(0.15)
            else:
                raise


def _write_legacy_session_registry_snapshot(registry_path: str | Path, database_path: str | Path) -> Path:
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = list_session_entries(database_path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _resolve_audio_recorder(audio_recorder: AudioRecorder | None, prefer_microphone: bool) -> AudioRecorder:
    if audio_recorder is not None:
        return audio_recorder

    microphone_status = microphone_capture_status()
    can_capture = bool(microphone_status.get("can_capture", False))

    if prefer_microphone and can_capture:
        return CallAudioRecorder()

    if prefer_microphone and not can_capture:
        if not microphone_runtime_available():
            raise RuntimeError(
                "Real microphone capture was requested, but the sounddevice runtime is not installed. "
                "Install sounddevice or start the session without microphone capture."
            )
        message = str(microphone_status.get("message", "")).strip() or (
            "Real microphone capture was requested, but Windows is not exposing a recording endpoint. "
            "Start the session without microphone capture."
        )
        raise RuntimeError(message)

    if can_capture:
        return CallAudioRecorder()

    return ScriptedAudioRecorder()


def save_session_registry_entry(runner: DesktopSessionRunner, destination: str | Path | None = None) -> Path:
    if runner.session_id is None:
        raise RuntimeError("Session runner must have a session ID before saving the registry entry.")

    registry_path = runner.resolve_session_registry_path(destination)
    database_path = runner.resolve_session_database_path()
    existing_entry = get_session_entry(database_path, runner.session_id) or {}
    worker_state_path = runner.resolve_session_worker_state_path()
    worker_status = "stopped"
    if worker_state_path.exists():
        worker_status = str(load_session_worker_state(worker_state_path).get("status", worker_status))
    existing_state = get_session_state(database_path, runner.session_id) or {}
    entry = {
        "session_id": runner.session_id,
        "profile_directory": str(runner.controller.profile_directory),
        "profile_name": runner.controller.profile.identity.full_name,
        "company_name": runner.controller.strategy_pack.company_brief.company_name,
        "role_title": runner.controller.strategy_pack.company_brief.role_title,
        "meeting_source": str(existing_state.get("meeting_source", "Manual / generic interview") or "Manual / generic interview"),
        "microphone_enabled": runner.prefer_microphone,
        "session_state_path": str(runner.resolve_session_state_path()),
        "session_command_queue_path": str(runner.resolve_session_command_queue_path()),
        "session_database_path": str(database_path),
        "session_worker_state_path": str(worker_state_path),
        "worker_status": worker_status,
        "tags": existing_entry.get("tags", []),
        "notes": existing_entry.get("notes", ""),
        "updated_at": _utc_now_iso(),
    }
    upsert_session_entry(database_path, entry)
    _write_legacy_session_registry_snapshot(registry_path, database_path)
    return registry_path


def find_session_registry_entry(session_id: str, registry_path: str | Path | None = None) -> dict[str, object]:
    database_entry = get_session_entry(session_database_path_from_registry_path(registry_path), session_id)
    if database_entry is None:
        raise KeyError(f"Session ID not found: {session_id}")
    return database_entry


def load_registered_session_state(session_id: str, registry_path: str | Path | None = None) -> dict[str, object]:
    database_payload = get_session_state(session_database_path_from_registry_path(registry_path), session_id)
    if database_payload is None:
        raise KeyError(f"Session state not found for session ID: {session_id}")
    if not database_payload.get("session_id"):
        database_payload["session_id"] = session_id
    return database_payload


def update_registered_session_state(
    session_id: str,
    updates: dict[str, object],
    registry_path: str | Path | None = None,
) -> dict[str, object]:
    payload = load_registered_session_state(session_id, registry_path)
    payload.update(updates)
    payload["updated_at"] = _utc_now_iso()

    database_path = session_database_path_from_registry_path(registry_path)
    upsert_session_state(database_path, session_id, payload)

    entry = find_session_registry_entry(session_id, registry_path)
    entry["updated_at"] = str(payload["updated_at"])
    entry["meeting_source"] = str(payload.get("meeting_source", entry.get("meeting_source", "Manual / generic interview")) or "Manual / generic interview")
    upsert_session_entry(database_path, entry)
    _write_legacy_session_registry_snapshot(
        Path(registry_path) if registry_path is not None else default_session_registry_path(),
        database_path,
    )
    return payload

def cleanup_stale_session_entries(registry_path: str | Path | None = None) -> list[str]:
    resolved_registry_path = Path(registry_path) if registry_path is not None else default_session_registry_path()
    database_path = session_database_path_from_registry_path(resolved_registry_path)
    removed_session_ids: list[str] = []

    for session_id, entry in load_session_registry(resolved_registry_path).items():
        profile_directory = Path(str(entry.get("profile_directory", "") or ""))
        if profile_directory.exists():
            continue
        delete_session(database_path, session_id)
        removed_session_ids.append(session_id)

    _write_legacy_session_registry_snapshot(resolved_registry_path, database_path)
    return removed_session_ids


def build_registered_session_runner(
    session_id: str,
    registry_path: str | Path | None = None,
    config_dir: str | Path | None = None,
    use_global_hotkeys: bool = False,
    audio_recorder: AudioRecorder | None = None,
    prefer_microphone: bool | None = None,
    stt_engine: STTEngine | None = None,
    llm_base_url: str | None = None,
    llm_timeout_seconds: float | None = None,
    overlay_controller: LiveOverlayController | None = None,
    session_database_path: str | Path | None = None,
) -> DesktopSessionRunner:
    entry = find_session_registry_entry(session_id, registry_path)
    runner = build_session_runner(
        profile_directory=Path(str(entry["profile_directory"])),
        company_name=str(entry["company_name"]),
        role_title=str(entry["role_title"]),
        config_dir=Path(config_dir) if config_dir is not None else None,
        use_global_hotkeys=use_global_hotkeys,
        audio_recorder=audio_recorder,
        prefer_microphone=bool(entry.get("microphone_enabled", False)) if prefer_microphone is None else prefer_microphone,
        stt_engine=stt_engine,
        llm_base_url=llm_base_url,
        llm_timeout_seconds=llm_timeout_seconds,
        overlay_controller=overlay_controller,
        session_state_path=Path(str(entry["session_state_path"])),
        session_registry_path=Path(registry_path) if registry_path is not None else None,
        session_command_queue_path=Path(str(entry["session_command_queue_path"])),
        session_database_path=Path(session_database_path) if session_database_path is not None else Path(str(entry.get("session_database_path", session_database_path_from_registry_path(registry_path)))),
        session_worker_state_path=Path(str(entry["session_worker_state_path"])) if entry.get("session_worker_state_path") else None,
    )
    runner.session_id = session_id
    return runner


def enqueue_session_command(
    session_id: str,
    command: str,
    registry_path: str | Path | None = None,
    fallback_action: str | None = None,
    diagnostics_destination: str | Path | None = None,
) -> Path:
    entry = find_session_registry_entry(session_id, registry_path)
    queue_path = Path(str(entry["session_command_queue_path"]))
    queued_commands = load_session_command_queue(queue_path)
    queued_commands.append(
        {
            "command": command,
            "fallback_action": fallback_action or "",
            "diagnostics_destination": str(diagnostics_destination) if diagnostics_destination is not None else "",
            "queued_at": _utc_now_iso(),
        }
    )
    return save_session_command_queue(queue_path, queued_commands)


def process_session_command_queue(runner: DesktopSessionRunner) -> list[str]:
    queue_path = runner.resolve_session_command_queue_path()
    queued_commands = load_session_command_queue(queue_path)
    if not queued_commands:
        return []

    results: list[str] = []
    for queued_command in queued_commands:
        if str(queued_command["command"]) == "stop-worker":
            results.append("Worker stop requested.")
            continue
        diagnostics_destination = queued_command.get("diagnostics_destination") or None
        results.append(
            execute_runner_command(
                runner,
                str(queued_command["command"]),
                fallback_action=str(queued_command.get("fallback_action") or "") or None,
                diagnostics_destination=Path(str(diagnostics_destination)) if diagnostics_destination else None,
            )
        )

    save_session_command_queue(queue_path, [])
    return results


def _worker_state_path_for_entry(session_id: str, entry: dict[str, object]) -> Path:
    if entry.get("session_worker_state_path"):
        return Path(str(entry["session_worker_state_path"]))
    return Path(str(entry["profile_directory"])) / f"{session_id}_{SESSION_WORKER_STATE_FILENAME}"


def run_session_worker(
    session_id: str,
    registry_path: str | Path | None = None,
    config_dir: str | Path | None = None,
    use_global_hotkeys: bool = False,
    llm_base_url: str | None = None,
    llm_timeout_seconds: float | None = None,
    session_database_path: str | Path | None = None,
    poll_interval_seconds: float = 0.25,
    max_polls: int | None = None,
) -> str:
    runner = build_registered_session_runner(
        session_id,
        registry_path=registry_path,
        config_dir=config_dir,
        use_global_hotkeys=use_global_hotkeys,
        llm_base_url=llm_base_url,
        llm_timeout_seconds=llm_timeout_seconds,
        session_database_path=session_database_path,
    )
    worker_state_path = runner.resolve_session_worker_state_path()
    started_at = _utc_now_iso()
    processed_commands = 0
    poll_count = 0
    last_command = ""
    last_result = ""
    last_error = ""
    final_status = "stopped"

    def persist_state(status: str, stopped_at: str = "", error_message: str | None = None) -> None:
        nonlocal last_error
        if error_message is not None:
            last_error = error_message
        save_session_worker_state(
            worker_state_path,
            {
                "session_id": session_id,
                "status": status,
                "started_at": started_at,
                "last_heartbeat_at": _utc_now_iso(),
                "stopped_at": stopped_at,
                "processed_commands": processed_commands,
                "poll_count": poll_count,
                "last_command": last_command,
                "last_result": last_result,
                "last_error": last_error,
            },
        )
        save_session_registry_entry(runner, registry_path)

    try:
        runner.start()
        persist_state("running")

        while True:
            poll_count += 1
            queued_commands = load_session_command_queue(runner.resolve_session_command_queue_path())
            stop_requested = False

            if queued_commands:
                save_session_command_queue(runner.resolve_session_command_queue_path(), [])
                for queued_command in queued_commands:
                    last_command = str(queued_command["command"])
                    if last_command == "stop-worker":
                        last_result = "Worker stop requested."
                        stop_requested = True
                        continue

                    diagnostics_destination = queued_command.get("diagnostics_destination") or None
                    last_result = execute_runner_command(
                        runner,
                        last_command,
                        fallback_action=str(queued_command.get("fallback_action") or "") or None,
                        diagnostics_destination=Path(str(diagnostics_destination)) if diagnostics_destination else None,
                    )
                    processed_commands += 1

            persist_state("running")

            if stop_requested:
                final_status = "stopped"
                break

            if max_polls is not None and poll_count >= max_polls:
                final_status = "idle"
                break

            time.sleep(max(0.05, poll_interval_seconds))
    except Exception as error:
        final_status = "failed"
        persist_state(final_status, stopped_at=_utc_now_iso(), error_message=str(error))
        raise
    finally:
        runner.stop()
        persist_state(final_status, stopped_at=_utc_now_iso(), error_message=None)

    return (
        f"Worker finished for session {session_id}\n"
        f"Status: {final_status}\n"
        f"Polls: {poll_count}\n"
        f"Processed commands: {processed_commands}"
    )


def get_session_worker_status(session_id: str, registry_path: str | Path | None = None) -> str:
    entry = find_session_registry_entry(session_id, registry_path)
    worker_state_path = _worker_state_path_for_entry(session_id, entry)
    if not worker_state_path.exists():
        return f"No worker state found for session {session_id}."

    payload = load_session_worker_state(worker_state_path)
    return (
        f"Worker session: {session_id}\n"
        f"Status: {payload.get('status', 'unknown')}\n"
        f"Processed commands: {payload.get('processed_commands', 0)}\n"
        f"Last command: {payload.get('last_command', '')}\n"
        f"Heartbeat: {payload.get('last_heartbeat_at', '')}"
    )


def list_sessions(registry_path: str | Path | None = None) -> str:
    registry = load_session_registry(registry_path)
    if not registry:
        return "No sessions found in the registry."

    lines = [f"Found {len(registry)} saved session(s):\n"]
    for session_id, entry in registry.items():
        lines.append(f"- {session_id}")
        lines.append(f"  Profile: {entry.get('profile_name', 'unknown')}")
        lines.append(f"  Company: {entry.get('company_name', 'unknown')}")
        lines.append(f"  Role: {entry.get('role_title', 'unknown')}")
        lines.append(f"  Updated: {entry.get('updated_at', 'unknown')}")
    return "\n".join(lines)


def register_web_session(
    profile_directory: str | Path,
    company_name: str,
    role_title: str,
    profile_name: str,
    *,
    registry_path: str | Path,
    prefer_microphone: bool = True,
    operator_prompts: dict[str, str] | None = None,
    extra_state: dict[str, object] | None = None,
) -> str:
    """Register a dashboard session without starting desktop audio/Qt controllers."""
    registry = Path(registry_path)
    database_path = session_database_path_from_registry_path(registry)
    profile_dir = Path(profile_directory)
    session_id = build_session_id(profile_name, company_name, role_title)
    session_state_path = profile_dir / SESSION_STATE_FILENAME
    command_queue_path = profile_dir / f"{session_id}_{SESSION_COMMAND_QUEUE_FILENAME}"
    worker_state_path = profile_dir / f"{session_id}_{SESSION_WORKER_STATE_FILENAME}"
    now = _utc_now_iso()

    entry = {
        "session_id": session_id,
        "profile_directory": str(profile_dir),
        "profile_name": profile_name,
        "company_name": company_name,
        "role_title": role_title,
        "microphone_enabled": prefer_microphone,
        "session_state_path": str(session_state_path),
        "session_command_queue_path": str(command_queue_path),
        "session_database_path": str(database_path),
        "session_worker_state_path": str(worker_state_path),
        "worker_status": "running",
        "tags": [],
        "notes": "",
        "updated_at": now,
    }
    upsert_session_entry(database_path, entry)

    state_payload: dict[str, object] = {
        "session_id": session_id,
        "started": True,
        "session_armed": True,
        "microphone_enabled": prefer_microphone,
        "profile_name": profile_name,
        "company_name": company_name,
        "role_title": role_title,
        "meeting_source": "Manual / generic interview",
        "meeting_capture_mode": "Companion workspace with live mic capture",
        "overlay_status": "idle",
        "overlay_visible": False,
        "turn_count": 0,
        "updated_at": now,
    }
    if operator_prompts:
        state_payload.update(operator_prompts)
    if extra_state:
        state_payload.update(extra_state)
    upsert_session_state(database_path, session_id, state_payload)
    _write_legacy_session_registry_snapshot(registry, database_path)
    return session_id


def cleanup_sessions(hours_old: int = 24, registry_path: str | Path | None = None) -> str:
    from datetime import timedelta

    resolved_registry_path = Path(registry_path) if registry_path is not None else default_session_registry_path()
    database_path = session_database_path_from_registry_path(resolved_registry_path)
    registry = load_session_registry(resolved_registry_path)
    if not registry:
        return "No sessions to clean up."

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=hours_old)
    removed_count = 0

    for session_id, entry in list(registry.items()):
        updated_at_str = str(entry.get("updated_at", ""))
        try:
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if updated_at < threshold:
                delete_session(database_path, session_id)
                removed_count += 1
        except (ValueError, TypeError):
            pass

    if removed_count > 0:
        _write_legacy_session_registry_snapshot(resolved_registry_path, database_path)
        return f"Cleaned up {removed_count} session(s) older than {hours_old} hours."

    return f"No sessions older than {hours_old} hours found."


def get_session_metrics(registry_path: str | Path | None = None) -> str:
    registry = load_session_registry(registry_path)
    if not registry:
        return "No sessions found. Run your first interview session to see metrics."
    
    total_sessions = len(registry)
    turn_counts = []
    profiles = set()
    companies = set()
    roles = set()
    
    database_path = session_database_path_from_registry_path(registry_path)
    for session_id, entry in registry.items():
        profiles.add(entry.get("profile_name", "unknown"))
        companies.add(entry.get("company_name", "unknown"))
        roles.add(entry.get("role_title", "unknown"))
        
        payload = get_session_state(database_path, session_id)
        if payload is not None:
            turn_counts.append(int(payload.get("turn_count", 0)))
    
    avg_turns = sum(turn_counts) / len(turn_counts) if turn_counts else 0
    completed_sessions = sum(1 for count in turn_counts if count > 0)
    completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    lines = [
        "═" * 50,
        "SESSION METRICS REPORT",
        "═" * 50,
        "",
        f"Total sessions: {total_sessions}",
        f"Completed sessions: {completed_sessions}",
        f"Completion rate: {completion_rate:.1f}%",
        f"Average turns per session: {avg_turns:.1f}",
        "",
        f"Unique profiles: {len(profiles)}",
        f"Unique companies: {len(companies)}",
        f"Unique roles: {len(roles)}",
        "",
        "═" * 50,
    ]
    
    return "\n".join(lines)


def export_session_html(session_id: str, output_path: str | Path | None = None, registry_path: str | Path | None = None) -> str:
    try:
        entry = find_session_registry_entry(session_id, registry_path)
        payload = load_registered_session_state(session_id, registry_path)
    except KeyError:
        raise ValueError(f"Session not found: {session_id}")
    
    # Determine output path
    if output_path is None:
        output_path = Path(str(entry["session_state_path"])).parent / f"{session_id}_export.html"
    else:
        output_path = Path(output_path)
    
    # Build HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interview Session Export - {session_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a73e8; margin-bottom: 30px; border-bottom: 3px solid #1a73e8; padding-bottom: 10px; }}
        h2 {{ color: #1a73e8; margin-top: 30px; margin-bottom: 15px; font-size: 1.3em; }}
        .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
        .meta-item {{ padding: 15px; background: #f9f9f9; border-left: 4px solid #1a73e8; border-radius: 4px; }}
        .meta-label {{ font-weight: 600; color: #666; font-size: 0.9em; }}
        .meta-value {{ color: #333; font-size: 1.05em; margin-top: 5px; }}
        .section {{ margin-bottom: 40px; }}
        .stat-box {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin: 20px 0; }}
        .stat {{ padding: 20px; background: #f0f7ff; border-radius: 6px; text-align: center; }}
        .stat-number {{ font-size: 2em; font-weight: bold; color: #1a73e8; }}
        .stat-label {{ color: #666; font-size: 0.9em; margin-top: 8px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f0f7ff; font-weight: 600; color: #1a73e8; }}
        tr:hover {{ background: #f9f9f9; }}
        .footer {{ text-align: center; padding-top: 20px; border-top: 1px solid #ddd; color: #999; font-size: 0.9em; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Interview Session Export</h1>
        
        <div class="section">
            <div class="meta-grid">
                <div class="meta-item">
                    <div class="meta-label">Session ID</div>
                    <div class="meta-value"><code>{payload.get('session_id', session_id)}</code></div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Profile</div>
                    <div class="meta-value">{entry.get('profile_name', 'Unknown')}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Company</div>
                    <div class="meta-value">{entry.get('company_name', 'Unknown')}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Role</div>
                    <div class="meta-value">{entry.get('role_title', 'Unknown')}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Session Started</div>
                    <div class="meta-value">{'Yes' if payload.get('started') else 'No'}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Last Updated</div>
                    <div class="meta-value">{entry.get('updated_at', 'Unknown')}</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Session Statistics</h2>
            <div class="stat-box">
                <div class="stat">
                    <div class="stat-number">{payload.get('turn_count', 0)}</div>
                    <div class="stat-label">Turns Completed</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{'Active' if payload.get('overlay_visible') else 'Inactive'}</div>
                    <div class="stat-label">Overlay Status</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{payload.get('overlay_status', 'Unknown')}</div>
                    <div class="stat-label">Current State</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Session Details</h2>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Session State Path</td>
                    <td><code>{payload.get('session_state_path', 'N/A')}</code></td>
                </tr>
                <tr>
                    <td>Overlay Status</td>
                    <td>{payload.get('overlay_status', 'Unknown')}</td>
                </tr>
                <tr>
                    <td>Overlay Visible</td>
                    <td>{'Yes' if payload.get('overlay_visible') else 'No'}</td>
                </tr>
                <tr>
                    <td>Interview Turns</td>
                    <td>{payload.get('turn_count', 0)}</td>
                </tr>
            </table>
        </div>
        
        <div class="footer">
            <p>Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p>Career Copilot Premium - Session Export Report</p>
        </div>
    </div>
</body>
</html>"""
    
    # Write HTML to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    
    return f"Session exported to: {output_path}"


def add_session_tag(session_id: str, tag: str, registry_path: str | Path | None = None) -> str:
    """Add a tag to a session registry entry."""
    entry = dict(find_session_registry_entry(session_id, registry_path))
    if "tags" not in entry:
        entry["tags"] = []
    
    tags = entry["tags"]
    if isinstance(tags, list):
        if tag not in tags:
            tags.append(tag)
    else:
        entry["tags"] = [tag]
    
    entry["updated_at"] = _utc_now_iso()
    upsert_session_entry(session_database_path_from_registry_path(registry_path), entry)
    
    return f"Tag '{tag}' added to session {session_id}."


def remove_session_tag(session_id: str, tag: str, registry_path: str | Path | None = None) -> str:
    """Remove a tag from a session registry entry."""
    entry = dict(find_session_registry_entry(session_id, registry_path))
    if "tags" not in entry:
        return f"No tags found for session {session_id}."
    
    tags = entry.get("tags", [])
    if tag in tags:
        tags.remove(tag)
        entry["updated_at"] = _utc_now_iso()
        upsert_session_entry(session_database_path_from_registry_path(registry_path), entry)
        
        return f"Tag '{tag}' removed from session {session_id}."
    
    return f"Tag '{tag}' not found in session {session_id}."


def set_session_notes(session_id: str, notes: str, registry_path: str | Path | None = None) -> str:
    """Set or update notes for a session registry entry."""
    entry = dict(find_session_registry_entry(session_id, registry_path))
    entry["notes"] = notes
    entry["updated_at"] = _utc_now_iso()
    upsert_session_entry(session_database_path_from_registry_path(registry_path), entry)
    
    return f"Notes updated for session {session_id}."


def get_session_metadata(session_id: str, registry_path: str | Path | None = None) -> str:
    """Get tags and notes for a session."""
    try:
        entry = find_session_registry_entry(session_id, registry_path)
    except KeyError:
        raise ValueError(f"Session not found: {session_id}")
    
    tags = entry.get("tags", [])
    notes = entry.get("notes", "")
    
    lines = [
        f"Session: {session_id}",
        f"Profile: {entry.get('profile_name', 'Unknown')}",
        f"Company: {entry.get('company_name', 'Unknown')}",
        f"Role: {entry.get('role_title', 'Unknown')}",
        "",
    ]
    
    if tags:
        lines.append(f"Tags ({len(tags)}): {', '.join(tags)}")
    else:
        lines.append("Tags: None")
    
    if notes:
        lines.append("")
        lines.append("Notes:")
        lines.append(notes)
    
    return "\n".join(lines)


def compare_sessions(
    primary_session_id: str,
    secondary_session_id: str,
    registry_path: str | Path | None = None,
) -> str:
    """Compare two saved sessions using registry metadata and persisted state."""
    try:
        primary_entry = find_session_registry_entry(primary_session_id, registry_path)
        secondary_entry = find_session_registry_entry(secondary_session_id, registry_path)
    except KeyError as error:
        raise ValueError(str(error)) from error

    primary_payload = load_registered_session_state(primary_session_id, registry_path)
    secondary_payload = load_registered_session_state(secondary_session_id, registry_path)

    primary_turns = int(primary_payload.get("turn_count", 0))
    secondary_turns = int(secondary_payload.get("turn_count", 0))
    turn_delta = primary_turns - secondary_turns

    lines = [
        "SESSION COMPARISON",
        f"Primary session: {primary_session_id}",
        f"Secondary session: {secondary_session_id}",
        "",
        f"Profile names: {primary_entry.get('profile_name', 'Unknown')} | {secondary_entry.get('profile_name', 'Unknown')}",
        f"Companies: {primary_entry.get('company_name', 'Unknown')} | {secondary_entry.get('company_name', 'Unknown')}",
        f"Roles: {primary_entry.get('role_title', 'Unknown')} | {secondary_entry.get('role_title', 'Unknown')}",
        f"Started: {primary_payload.get('started', False)} | {secondary_payload.get('started', False)}",
        f"Overlay status: {primary_payload.get('overlay_status', 'unknown')} | {secondary_payload.get('overlay_status', 'unknown')}",
        f"Overlay visible: {primary_payload.get('overlay_visible', False)} | {secondary_payload.get('overlay_visible', False)}",
        f"Turn count: {primary_turns} | {secondary_turns}",
        f"Turn delta (primary-secondary): {turn_delta}",
        f"Same company: {primary_entry.get('company_name') == secondary_entry.get('company_name')}",
        f"Same role: {primary_entry.get('role_title') == secondary_entry.get('role_title')}",
    ]
    return "\n".join(lines)


def _format_overlay_state(state: OverlayState) -> str:
    return (
        f"Overlay status: {state.status}\n"
        f"Overlay visible: {state.visible}\n"
        f"Provider status: {state.provider_status or 'n/a'}"
    )


def _build_runtime_with_overrides(
    config_dir: str | Path | None,
    llm_base_url: str | None,
    llm_timeout_seconds: float | None,
) -> "DesktopRuntime":
    from .main import apply_runtime_overrides, build_desktop_runtime

    runtime = build_desktop_runtime(Path(config_dir) if config_dir else None)
    return apply_runtime_overrides(
        runtime,
        llm_base_url=llm_base_url,
        llm_timeout_seconds=llm_timeout_seconds,
    )


def build_desktop_session(
    profile_directory: str | Path,
    company_name: str,
    role_title: str,
    config_dir: str | Path | None = None,
    use_global_hotkeys: bool = False,
    audio_recorder: AudioRecorder | None = None,
    prefer_microphone: bool = True,
    stt_engine: STTEngine | None = None,
    llm_base_url: str | None = None,
    llm_timeout_seconds: float | None = None,
    overlay_controller: LiveOverlayController | None = None,
) -> DesktopSessionController:
    runtime = _build_runtime_with_overrides(config_dir, llm_base_url, llm_timeout_seconds)
    resolved_profile_directory = Path(profile_directory)
    if not is_session_ready(resolved_profile_directory):
        raise PermissionError("Desktop session cannot start until a resume-backed profile is ready.")

    profile = load_completed_profile(resolved_profile_directory / PROFILE_FILENAME)
    strategy_pack = generate_strategy_pack(profile, company_name=company_name, role_title=role_title)
    hotkey_manager = HotkeyManager(use_global_backend=use_global_hotkeys)
    session_overlay_controller = overlay_controller or create_overlay_controller(theme=runtime.runtime_config.app.theme)
    interview_mode = DesktopInterviewMode(
        profile_directory=resolved_profile_directory,
        strategy_pack=strategy_pack,
        audio_recorder=_resolve_audio_recorder(audio_recorder, prefer_microphone),
        stt_engine=stt_engine or runtime.stt_engine,
        answer_engine=runtime.answer_engine,
        hotkey_manager=hotkey_manager,
        overlay_opacity=runtime.runtime_config.app.overlay_opacity,
        hotkey=runtime.runtime_config.app.hotkey,
    )
    return DesktopSessionController(
        runtime=runtime,
        profile_directory=resolved_profile_directory,
        profile=profile,
        strategy_pack=strategy_pack,
        interview_mode=interview_mode,
        overlay_controller=session_overlay_controller,
    )


def build_desktop_session_runtime(
    profile_directory: str | Path,
    company_name: str,
    role_title: str,
    config_dir: str | Path | None = None,
    use_global_hotkeys: bool = False,
    audio_recorder: AudioRecorder | None = None,
    prefer_microphone: bool = True,
    stt_engine: STTEngine | None = None,
    llm_base_url: str | None = None,
    llm_timeout_seconds: float | None = None,
) -> tuple[DesktopSessionController, OverlayRuntime]:
    runtime = _build_runtime_with_overrides(config_dir, llm_base_url, llm_timeout_seconds)
    overlay_runtime = create_overlay_runtime(theme=runtime.runtime_config.app.theme)
    controller = build_desktop_session(
        profile_directory=profile_directory,
        company_name=company_name,
        role_title=role_title,
        config_dir=config_dir,
        use_global_hotkeys=use_global_hotkeys,
        audio_recorder=audio_recorder,
        prefer_microphone=prefer_microphone,
        stt_engine=stt_engine,
        llm_base_url=llm_base_url,
        llm_timeout_seconds=llm_timeout_seconds,
        overlay_controller=overlay_runtime.controller,
    )
    return controller, overlay_runtime


def build_session_runner(
    profile_directory: str | Path,
    company_name: str,
    role_title: str,
    config_dir: str | Path | None = None,
    use_global_hotkeys: bool = False,
    audio_recorder: AudioRecorder | None = None,
    prefer_microphone: bool = True,
    stt_engine: STTEngine | None = None,
    llm_base_url: str | None = None,
    llm_timeout_seconds: float | None = None,
    overlay_controller: LiveOverlayController | None = None,
    session_state_path: str | Path | None = None,
    session_registry_path: str | Path | None = None,
    session_command_queue_path: str | Path | None = None,
    session_database_path: str | Path | None = None,
    session_worker_state_path: str | Path | None = None,
) -> DesktopSessionRunner:
    controller = build_desktop_session(
        profile_directory=profile_directory,
        company_name=company_name,
        role_title=role_title,
        config_dir=config_dir,
        use_global_hotkeys=use_global_hotkeys,
        audio_recorder=audio_recorder,
        prefer_microphone=prefer_microphone,
        stt_engine=stt_engine,
        llm_base_url=llm_base_url,
        llm_timeout_seconds=llm_timeout_seconds,
        overlay_controller=overlay_controller,
    )
    return DesktopSessionRunner(
        controller=controller,
        session_state_path=Path(session_state_path) if session_state_path is not None else None,
        session_registry_path=Path(session_registry_path) if session_registry_path is not None else None,
        session_command_queue_path=Path(session_command_queue_path) if session_command_queue_path is not None else None,
        session_database_path=Path(session_database_path) if session_database_path is not None else None,
        session_worker_state_path=Path(session_worker_state_path) if session_worker_state_path is not None else None,
        prefer_microphone=prefer_microphone,
    )


def build_session_summary(controller: DesktopSessionController, strategy_path: Path) -> str:
    return (
        f"Session armed for {controller.profile.identity.full_name}\n"
        f"Company: {controller.strategy_pack.company_brief.company_name}\n"
        f"Role: {controller.strategy_pack.company_brief.role_title}\n"
        f"Hotkey: {controller.interview_mode.hotkey}\n"
        f"STT engine: {type(controller.runtime.stt_engine).__name__}\n"
        f"LLM endpoint: {controller.runtime.runtime_config.model.llm_base_url}\n"
        f"Answer engine: {type(controller.runtime.answer_engine).__name__}\n"
        f"Strategy saved: {strategy_path}"
    )