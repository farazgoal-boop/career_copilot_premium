"""Live HTTP bridge for mobile shells and Android bubble surfaces."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import socket
import sys
from threading import Thread
import time
import traceback
from typing import Any
from urllib.parse import unquote, urlsplit

from app_licensing import current_license_status, is_machine_licensed
from desktop_app.audio_handler import microphone_capture_status
from desktop_app.runtime_controller import (
    build_session_runner,
    execute_runner_command,
    load_session_registry,
    run_session_worker,
)
from runtime_paths import (
    default_bridge_base_url,
    pairing_codes_path,
    profiles_root,
    resolve_data_root,
    resolve_public_bridge_host,
    session_registry_path,
)
from .contracts import MobileBridgeSnapshot
from .runtime_bridge import build_mobile_bridge_snapshot_for_session, enqueue_mobile_bridge_action


_WORKER_THREADS: dict[str, Thread] = {}
PAIRING_CODE_TTL_SECONDS = 300  # 5 minutes — keep QR pairing short-lived for safety


@dataclass
class PairingRecord:
    code: str
    session_id: str | None
    created_at: float
    expires_at: float
    consumed: bool = False


_PAIRING_CODES: dict[str, PairingRecord] = {}
_MOBILE_LAST_SEEN: float = 0.0
_MOBILE_SESSION_ID: str = ""


def touch_mobile_connection(session_id: str = "") -> None:
    global _MOBILE_LAST_SEEN, _MOBILE_SESSION_ID
    _MOBILE_LAST_SEEN = time.time()
    if session_id:
        _MOBILE_SESSION_ID = session_id


def mobile_connection_status(within_seconds: float = 90.0) -> dict[str, object]:
    connected = (time.time() - _MOBILE_LAST_SEEN) > 0 and (time.time() - _MOBILE_LAST_SEEN) <= within_seconds
    last_seen = ""
    if _MOBILE_LAST_SEEN > 0:
        from datetime import datetime, timezone

        last_seen = datetime.fromtimestamp(_MOBILE_LAST_SEEN, tz=timezone.utc).isoformat()
    return {
        "connected": connected,
        "last_seen": last_seen,
        "session_id": _MOBILE_SESSION_ID if connected else "",
    }


def _normalize_pairing_code(raw_code: object) -> str:
    """Normalize pairing codes to avoid case and whitespace mismatches."""
    return str(raw_code).strip().upper()


def _resolved_pairing_bridge_url(base_url: str | None = None) -> str:
    """Return a mobile-reachable bridge URL and avoid localhost in confirm responses."""
    candidate = str(base_url or os.environ.get("BRIDGE_BASE_URL") or default_bridge_base_url()).strip()
    if not candidate:
        candidate = default_bridge_base_url()
    if "127.0.0.1" in candidate or "localhost" in candidate.lower():
        candidate = default_bridge_base_url()
    return candidate.rstrip("/")


def build_live_bridge_payload(
    snapshot: MobileBridgeSnapshot,
    base_url: str | None = None,
) -> dict[str, object]:
    action_items: list[dict[str, object]] = []
    for action in snapshot.actions:
        action_items.append(
            {
                "action_id": action.action_id,
                "label": action.label,
                "session_command": action.session_command,
                "fallback_action": action.fallback_action,
                "href": (
                    f"{base_url.rstrip('/')}/session/{snapshot.session_id}/actions/{action.action_id}"
                    if base_url
                    else f"/session/{snapshot.session_id}/actions/{action.action_id}"
                ),
                "method": "POST",
            }
        )

    return {
        "snapshot": snapshot.to_dict(),
        "microphone": microphone_capture_status(),
        "readiness": _build_readiness_payload(snapshot),
        "prompts": {
            "persistent": snapshot.persistent_prompt,
            "live": snapshot.live_prompt,
        },
        "overlay": {
            "mode": "expanded" if snapshot.bubble.visible else "compact",
            "status": snapshot.bubble.status,
            "headline": snapshot.bubble.headline,
            "body": snapshot.bubble.body,
            "confidence_score": snapshot.bubble.confidence_score,
            "provider_status": snapshot.bubble.provider_status,
            "alternatives": list(snapshot.bubble.alternatives),
            "actions": action_items,
        },
        "transport": {
            "protocol": "http",
            "base_url": base_url or "",
            "session_href": (
                f"{base_url.rstrip('/')}/session/{snapshot.session_id}"
                if base_url
                else f"/session/{snapshot.session_id}"
            ),
        },
    }


def _build_readiness_payload(snapshot: MobileBridgeSnapshot) -> dict[str, str]:
    if snapshot.bubble.status == "answer_ready":
        return {
            "label": "Ready",
            "title": "Reply ready",
            "hint": "AI has drafted a primary reply and fallback options for the current interviewer prompt.",
            "tone": "ready",
            "call_label": "Question captured",
            "call_tone": "ready",
            "workspace_mode": "answer_ready",
        }

    if snapshot.bubble.status == "listening":
        return {
            "label": "Listening",
            "title": "Listening live",
            "hint": "Microphone capture is active and the assistant is waiting for the next interviewer prompt.",
            "tone": "listening",
            "call_label": "Live capture",
            "call_tone": "listening",
            "workspace_mode": "listening",
        }

    if snapshot.session_armed or snapshot.worker_status == "running":
        return {
            "label": "Armed",
            "title": "Waiting for the next question",
            "hint": "The interview workspace is prepared and ready to switch into listening or answer generation.",
            "tone": "armed",
            "call_label": "Waiting for caller",
            "call_tone": "armed",
            "workspace_mode": "armed",
        }

    return {
        "label": "Idle",
        "title": "Standby",
        "hint": "Load a session and use the live controls to prepare for the next question.",
        "tone": "neutral",
        "call_label": "Standby",
        "call_tone": "standby",
        "workspace_mode": "standby",
    }


def build_live_bridge_payload_for_session(
    session_id: str,
    registry_path: str | Path | None = None,
    base_url: str | None = None,
) -> dict[str, object]:
    snapshot = build_mobile_bridge_snapshot_for_session(session_id, registry_path)
    return build_live_bridge_payload(snapshot, base_url=base_url)


def build_live_sessions_payload(
    registry_path: str | Path | None = None,
    base_url: str | None = None,
) -> dict[str, object]:
    registry = load_session_registry(registry_path)
    sessions: list[dict[str, str]] = []
    for session_id, entry in registry.items():
        sessions.append(
            {
                "session_id": session_id,
                "profile_name": str(entry.get("profile_name", "")),
                "company_name": str(entry.get("company_name", "")),
                "role_title": str(entry.get("role_title", "")),
                "worker_status": str(entry.get("worker_status", "")),
                "updated_at": str(entry.get("updated_at", "")),
                "session_href": (
                    f"{base_url.rstrip('/')}/session/{session_id}" if base_url else f"/session/{session_id}"
                ),
            }
        )

    sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    latest_session_id = sessions[0]["session_id"] if sessions else ""
    return {
        "sessions": sessions,
        "latest_session_id": latest_session_id,
        "count": len(sessions),
    }


def _default_briefing_profile_dir() -> Path | None:
    """Return the most recently materialised briefing profile directory, if any."""
    candidates = _profile_roots()
    for base in candidates:
        if not base.exists():
            continue
        profile_dirs = sorted(
            [d for d in base.iterdir() if d.is_dir() and d != base],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if profile_dirs:
            return profile_dirs[0]
    return None


def _profile_roots() -> list[Path]:
    roots = [profiles_root(), Path(__file__).resolve().parents[1] / "data" / "user_profiles"]
    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in roots:
        normalized = str(candidate.resolve())
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates


def bootstrap_live_session(registry_path: str | Path | None = None) -> dict[str, object]:
    registry = load_session_registry(registry_path)
    latest_session_id = _latest_session_id_from_registry(registry)
    created_session = False

    if latest_session_id is None:
        profile_dir = _default_briefing_profile_dir()
        if profile_dir is None:
            raise ValueError(
                "No saved sessions found. Complete onboarding and tap Create Session first."
            )

        profile_name = profile_dir.name.replace("-", " ").title()
        runner = build_session_runner(
            profile_directory=profile_dir,
            company_name=profile_name,
            role_title=profile_name,
            session_registry_path=registry_path,
        )
        try:
            execute_runner_command(runner, "start")
            latest_session_id = runner.session_id
            created_session = True
        finally:
            runner.stop()

    if not latest_session_id:
        raise ValueError("Could not resolve or create a session ID.")

    worker_started = _ensure_worker_thread(latest_session_id, registry_path)
    return {
        "session_id": latest_session_id,
        "created_session": created_session,
        "worker_started": worker_started,
    }


def create_pairing_code(registry_path: str | Path | None = None) -> dict[str, object]:
    now = time.time()
    _prune_expired_pairing_codes(now)

    bootstrap = bootstrap_live_session(registry_path=registry_path)
    session_id = str(bootstrap.get("session_id", "")).strip()
    if not session_id:
        raise ValueError(
            "Link Device could not prepare a desktop session. Complete the wizard and click 'Create session' first."
        )

    code = _normalize_pairing_code(f"{secrets.randbelow(1_000_000):06d}")
    while code in _PAIRING_CODES and not _is_pairing_code_expired(_PAIRING_CODES[code], now):
        code = _normalize_pairing_code(f"{secrets.randbelow(1_000_000):06d}")

    expires_at = now + PAIRING_CODE_TTL_SECONDS
    _PAIRING_CODES[code] = PairingRecord(
        code=code,
        session_id=session_id,
        created_at=now,
        expires_at=expires_at,
    )
    save_pairing_codes_to_disk(_pairing_codes_cache_path())

    return {
        "pairing_code": code,
        "session_id": session_id,
        "session_ready": True,
        "worker_started": bool(bootstrap.get("worker_started", False)),
        "expires_in_seconds": PAIRING_CODE_TTL_SECONDS,
        "expires_at_unix": int(expires_at),
    }


def register_pairing_code(code: str, session_id: str | None) -> dict[str, object]:
    """Register/refresh a pairing code in the shared mobile bridge store."""
    normalized_code = _normalize_pairing_code(code)
    normalized_session_id = str(session_id or "").strip() or None
    if len(normalized_code) != 6:
        raise ValueError("Pairing code must be 6 digits.")

    now = time.time()
    disk_records = _read_pairing_codes_from_disk(_pairing_codes_cache_path())
    _PAIRING_CODES.clear()
    _PAIRING_CODES.update(disk_records)
    _prune_expired_pairing_codes(now)
    expires_at = now + PAIRING_CODE_TTL_SECONDS
    record = PairingRecord(
        code=normalized_code,
        session_id=normalized_session_id,
        created_at=now,
        expires_at=expires_at,
        consumed=False,
    )
    _PAIRING_CODES[normalized_code] = record
    save_pairing_codes_to_disk(_pairing_codes_cache_path())
    print(
        "[mobile-bridge] pairing code registered "
        f"code={normalized_code!r} session_id={normalized_session_id!r} expires_at={expires_at}"
    )
    return {
        "pairing_code": normalized_code,
        "session_id": normalized_session_id,
        "expires_in_seconds": PAIRING_CODE_TTL_SECONDS,
        "expires_at_unix": int(expires_at),
    }


def confirm_pairing_code(
    code: str,
    registry_path: str | Path | None = None,
    bridge_url: str | None = None,
) -> dict[str, object]:
    normalized_code = _normalize_pairing_code(code)
    disk_records = _read_pairing_codes_from_disk(_pairing_codes_cache_path())
    normalized_codes_in_store = {stored_code.strip().upper(): stored_code for stored_code in disk_records}
    print(
        "[mobile-bridge] pairing confirm request "
        f"incoming_raw={code!r} incoming_normalized={normalized_code!r} "
        f"stored_codes={list(normalized_codes_in_store.keys())}"
    )

    if len(normalized_code) != 6:
        raise ValueError("Pairing code must be 6 digits.")

    now = time.time()

    matched_code = normalized_codes_in_store.get(normalized_code)
    record = disk_records.get(matched_code or normalized_code)
    if record is None:
        print(
            "[mobile-bridge] pairing confirm failed: no matching code "
            f"for incoming={normalized_code!r}. Active records="
            f"{ {k: {'session_id': v.session_id, 'expires_at': v.expires_at, 'consumed': v.consumed} for k, v in disk_records.items()} }"
        )
        raise ValueError("Pairing code is invalid or expired.")
    if _is_pairing_code_expired(record, now):
        print(
            "[mobile-bridge] pairing confirm failed: code expired "
            f"code={record.code!r} expires_at={record.expires_at} now={now}"
        )
        disk_records.pop(record.code, None)
        _PAIRING_CODES.clear()
        _PAIRING_CODES.update(disk_records)
        save_pairing_codes_to_disk(_pairing_codes_cache_path())
        raise ValueError("Pairing code is invalid or expired.")
    if record.consumed:
        print(f"[mobile-bridge] pairing confirm failed: code already consumed code={record.code!r}")
        raise ValueError("Pairing code already used. Generate a new code on desktop.")

    session_id = record.session_id
    print(
        "[mobile-bridge] pairing confirm matched "
        f"code={record.code!r} session_id={session_id!r} consumed={record.consumed}"
    )
    if not session_id or session_id not in load_session_registry(registry_path):
        print(
            "[mobile-bridge] pairing confirm session check failed; "
            f"rebootstrapping session for code={record.code!r} existing_session_id={session_id!r}"
        )
        bootstrap = bootstrap_live_session(registry_path=registry_path)
        session_id = str(bootstrap.get("session_id", "")).strip()
        if not session_id:
            raise ValueError(
                "Pairing code is valid but no desktop session is ready. "
                "Complete the wizard and click 'Create session' first."
            )
        record.session_id = session_id

    record.consumed = True
    disk_records[record.code] = record
    _PAIRING_CODES.clear()
    _PAIRING_CODES.update(disk_records)
    save_pairing_codes_to_disk(_pairing_codes_cache_path())
    worker_started = _ensure_worker_thread(session_id, registry_path)
    touch_mobile_connection(session_id)
    resolved_bridge_url = _resolved_pairing_bridge_url(bridge_url)
    print(
        "[mobile-bridge] pairing confirm success "
        f"session_id={session_id!r} worker_started={worker_started} bridge_url={resolved_bridge_url!r}"
    )
    return {
        "session_id": session_id,
        "worker_started": worker_started,
        "bridge_url": resolved_bridge_url,
    }


def ensure_live_session_worker(session_id: str, registry_path: str | Path | None = None) -> bool:
    normalized_session_id = str(session_id).strip()
    if not normalized_session_id:
        raise ValueError("Session ID is required.")
    if normalized_session_id not in load_session_registry(registry_path):
        raise KeyError(f"Session ID not found: {normalized_session_id}")
    return _ensure_worker_thread(normalized_session_id, registry_path)


@dataclass
class MobileBridgeServer:
    server: ThreadingHTTPServer
    thread: Thread
    port: int = 0

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        resolved_host = resolve_public_bridge_host() if host in ("0.0.0.0", "") else host
        return f"http://{resolved_host}:{port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class _ReuseAddrHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    allow_reuse_port = True


def create_mobile_bridge_handler(registry_path: str | Path | None = None):
    resolved_registry_path = Path(registry_path) if registry_path is not None else None

    class MobileBridgeHandler(BaseHTTPRequestHandler):
        server_version = "CareerCopilotMobileBridge/1.0"

        def do_GET(self) -> None:  # noqa: N802
            request_path = _normalized_path(self.path)
            if request_path == "/health":
                self._send_json(HTTPStatus.OK, {"ok": True})
                return

            if request_path == "/sessions":
                if not is_machine_licensed():
                    self._send_license_required()
                    return
                try:
                    payload = build_live_sessions_payload(
                        registry_path=resolved_registry_path,
                        base_url=self._base_url(),
                    )
                except Exception as error:  # pragma: no cover - defensive handler for runtime issues.
                    self._log_internal_error("GET", request_path, error)
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {
                            "error": "Live bridge internal error.",
                            "hint": "Could not read session registry. Check desktop runtime logs.",
                        },
                    )
                    return

                self._send_json(HTTPStatus.OK, payload)
                return

            session_id = _parse_session_path(request_path)
            if session_id is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown route."})
                return

            if not is_machine_licensed():
                self._send_license_required()
                return

            try:
                touch_mobile_connection(session_id)
                payload = build_live_bridge_payload_for_session(
                    session_id,
                    registry_path=resolved_registry_path,
                    base_url=self._base_url(),
                )
            except KeyError as error:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except ValueError as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception as error:  # pragma: no cover - defensive handler for runtime issues.
                self._log_internal_error("GET", request_path, error)
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "Live bridge internal error.",
                        "hint": "Check desktop logs and verify the selected session is fully initialized.",
                    },
                )
                return

            self._send_json(HTTPStatus.OK, payload)

        def do_POST(self) -> None:  # noqa: N802
            request_path = _normalized_path(self.path)
            if request_path == "/bootstrap-session":
                try:
                    payload = bootstrap_live_session(registry_path=resolved_registry_path)
                except ValueError as error:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                    return
                except Exception as error:  # pragma: no cover - defensive handler for runtime issues.
                    self._log_internal_error("POST", request_path, error)
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {
                            "error": "Live bridge internal error.",
                            "hint": "Could not bootstrap a desktop session. Check desktop runtime logs.",
                        },
                    )
                    return

                self._send_json(HTTPStatus.OK, payload)
                return

            if request_path == "/pairing/create":
                try:
                    payload = create_pairing_code(registry_path=resolved_registry_path)
                except ValueError as error:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                    return
                except Exception as error:  # pragma: no cover - defensive handler for runtime issues.
                    self._log_internal_error("POST", request_path, error)
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {
                            "error": "Live bridge internal error.",
                            "hint": "Could not create pairing code. Check desktop runtime logs.",
                        },
                    )
                    return

                self._send_json(HTTPStatus.OK, payload)
                return

            if request_path == "/pairing/confirm":
                try:
                    content_length = int(self.headers.get("Content-Length", "0") or "0")
                    raw_payload = self.rfile.read(content_length) if content_length > 0 else b"{}"
                    body = json.loads(raw_payload.decode("utf-8") or "{}")
                    pairing_code = str(body.get("pairing_code", ""))
                    payload = confirm_pairing_code(
                        pairing_code,
                        registry_path=resolved_registry_path,
                        bridge_url=self._base_url(),
                    )
                except ValueError as error:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                    return
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."})
                    return
                except Exception as error:  # pragma: no cover - defensive handler for runtime issues.
                    self._log_internal_error("POST", request_path, error)
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {
                            "error": "Live bridge internal error.",
                            "hint": "Could not confirm pairing code. Check desktop runtime logs.",
                        },
                    )
                    return

                self._send_json(HTTPStatus.OK, payload)
                return

            parsed = _parse_action_path(request_path)
            if parsed is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown route."})
                return

            if not is_machine_licensed():
                self._send_license_required()
                return

            session_id, action_id = parsed
            try:
                touch_mobile_connection(session_id)
                if action_id == "listen":
                    from desktop_app.live_listen import build_listening_state_for_session, run_live_listen_cycle

                    build_listening_state_for_session(session_id, resolved_registry_path)
                    result = run_live_listen_cycle(session_id, registry_path=resolved_registry_path)
                    payload = build_live_bridge_payload_for_session(
                        session_id,
                        registry_path=resolved_registry_path,
                        base_url=self._base_url(),
                    )
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "queued_action": action_id,
                            "status": "completed",
                            "transcript": result.transcript,
                            "suggested_answer": result.suggested_answer,
                            **payload,
                        },
                    )
                    return

                ensure_live_session_worker(session_id, resolved_registry_path)
                snapshot = build_mobile_bridge_snapshot_for_session(session_id, resolved_registry_path)
                queue_path = enqueue_mobile_bridge_action(snapshot, action_id, resolved_registry_path)
                payload = build_live_bridge_payload_for_session(
                    session_id,
                    registry_path=resolved_registry_path,
                    base_url=self._base_url(),
                )
            except KeyError as error:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except ValueError as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception as error:  # pragma: no cover - defensive handler for runtime issues.
                self._log_internal_error("POST", request_path, error)
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "Live bridge internal error.",
                        "hint": str(error) or "Check desktop logs and verify the selected session is fully initialized.",
                    },
                )
                return

            self._send_json(
                HTTPStatus.ACCEPTED,
                {
                    "queued_action": action_id,
                    "queue_path": str(queue_path),
                    **payload,
                },
            )

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _base_url(self) -> str:
            host, port = self.server.server_address[:2]
            resolved_host = resolve_public_bridge_host() if host in ("0.0.0.0", "") else host
            return f"http://{resolved_host}:{port}"

        def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_license_required(self) -> None:
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {
                    "error": "Desktop activation required before mobile pairing can start.",
                    "license_required": True,
                    **current_license_status(),
                },
            )

        def _log_internal_error(self, method: str, path: str, error: BaseException) -> None:
            print(f"[mobile-bridge] {method} {path} failed: {error}")
            print(traceback.format_exc())

    return MobileBridgeHandler


def start_mobile_bridge_server(
    host: str = "0.0.0.0",
    port: int = 0,
    registry_path: str | Path | None = None,
) -> MobileBridgeServer:
    from runtime_paths import MOBILE_BRIDGE_PORT

    load_pairing_codes_from_disk(_pairing_codes_cache_path())
    handler = create_mobile_bridge_handler(registry_path)
    bind_port = port or MOBILE_BRIDGE_PORT
    last_error: OSError | None = None

    for candidate_port in range(bind_port, bind_port + 6):
        try:
            server = _ReuseAddrHTTPServer((host, candidate_port), handler)
            break
        except OSError as error:
            last_error = error
            server = None
    else:
        raise last_error or OSError(f"Could not bind mobile bridge on port {bind_port}")

    thread = Thread(target=server.serve_forever, name="career-copilot-mobile-bridge", daemon=True)
    thread.start()
    bound_port = int(server.server_address[1])
    return MobileBridgeServer(server=server, thread=thread, port=bound_port)


def serve_mobile_bridge(
    host: str = "0.0.0.0",
    port: int = 8765,
    registry_path: str | Path | None = None,
) -> str:
    load_pairing_codes_from_disk(_pairing_codes_cache_path())
    server = ThreadingHTTPServer((host, port), create_mobile_bridge_handler(registry_path))
    try:
        resolved_host, resolved_port = server.server_address[:2]
        server.serve_forever()
    finally:
        server.server_close()
    return f"http://{resolved_host}:{resolved_port}"


def _parse_session_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "session":
        return unquote(parts[1])
    return None


def _parse_action_path(path: str) -> tuple[str, str] | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 4 and parts[0] == "session" and parts[2] == "actions":
        return unquote(parts[1]), unquote(parts[3])
    return None


def _normalized_path(path: str) -> str:
    parsed = urlsplit(path)
    return parsed.path or "/"


def _latest_session_id_from_registry(registry: dict[str, dict[str, object]]) -> str | None:
    if not registry:
        return None

    sorted_items = sorted(
        registry.items(),
        key=lambda item: str(item[1].get("updated_at", "")),
        reverse=True,
    )
    return sorted_items[0][0] if sorted_items else None


def _ensure_worker_thread(session_id: str, registry_path: str | Path | None = None) -> bool:
    existing_thread = _WORKER_THREADS.get(session_id)
    if existing_thread and existing_thread.is_alive():
        return False

    def _worker() -> None:
        try:
            run_session_worker(session_id, registry_path=registry_path)
        except Exception as error:  # pragma: no cover - background worker safety.
            print(f"[mobile-bridge] worker for {session_id} failed: {error}")
            print(traceback.format_exc())

    thread = Thread(target=_worker, name=f"mobile-bridge-worker-{session_id}", daemon=True)
    _WORKER_THREADS[session_id] = thread
    thread.start()
    return True


def _is_pairing_code_expired(record: PairingRecord, now: float) -> bool:
    return now >= record.expires_at


def _prune_expired_pairing_codes(now: float) -> None:
    expired_codes = [code for code, record in _PAIRING_CODES.items() if record.consumed or _is_pairing_code_expired(record, now)]
    for code in expired_codes:
        _PAIRING_CODES.pop(code, None)
    if expired_codes:
        save_pairing_codes_to_disk(_pairing_codes_cache_path())


def _pairing_codes_cache_path() -> Path:
    """Disk path where active pairing codes are persisted to survive process restarts."""
    return pairing_codes_path(resolve_data_root())


def save_pairing_codes_to_disk(path: str | Path) -> None:
    """Write active, unexpired pairing codes to disk."""
    now = time.time()
    persisted = {
        code: {
            "code": record.code,
            "session_id": record.session_id,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
            "consumed": record.consumed,
        }
        for code, record in _PAIRING_CODES.items()
        if not _is_pairing_code_expired(record, now)
    }
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")
    except OSError:
        pass


def _read_pairing_codes_from_disk(path: str | Path) -> dict[str, PairingRecord]:
    """Read pairing records directly from the shared JSON cache file."""
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    try:
        raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    now = time.time()
    records: dict[str, PairingRecord] = {}
    for code, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        try:
            record = PairingRecord(
                code=_normalize_pairing_code(entry["code"]),
                session_id=str(entry.get("session_id", "")).strip() or None,
                created_at=float(entry["created_at"]),
                expires_at=float(entry["expires_at"]),
                consumed=bool(entry.get("consumed", False)),
            )
        except (KeyError, ValueError, TypeError):
            continue
        if _is_pairing_code_expired(record, now):
            continue
        records[record.code] = record
    return records


def load_pairing_codes_from_disk(path: str | Path) -> None:
    """Restore active pairing codes from disk into the in-memory dict."""
    records = _read_pairing_codes_from_disk(path)
    _PAIRING_CODES.clear()
    _PAIRING_CODES.update(records)


# Re-hydrate any pairing codes that were active when the process last stopped.
load_pairing_codes_from_disk(_pairing_codes_cache_path())