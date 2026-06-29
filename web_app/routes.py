"""HTTP routes for the live web dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

from flask import Flask, Response, current_app, jsonify, redirect, render_template, request, stream_with_context, url_for

from app_licensing import activate_machine_license, current_license_status, is_machine_licensed
from runtime_paths import (
    briefing_storage_path,
    default_bridge_base_url,
    profiles_root,
    session_registry_path,
)


DEFAULT_BRIEFING_ID = "primary"
_MIC_RUNTIME_CACHE: dict[str, object] | None = None


def _is_public_route(path: str) -> bool:
    normalized = (path or "/").rstrip("/").lower() or "/"
    if normalized.startswith("/static/"):
        return True
    return normalized in {
        "/",
        "/health",
        "/api/health",
        "/api/license/status",
        "/api/license/activate",
    }


def register_routes(app: Flask) -> None:
    @app.get("/api/health")
    def health() -> Response:
        return jsonify({"status": "ok"}), 200

    @app.get("/health")
    def health_compat() -> Response:
        return jsonify({"status": "ok"}), 200

    @app.before_request
    def require_machine_activation() -> Response | None:
        path = request.path or "/"
        if _is_public_route(path):
            return None
        if is_machine_licensed():
            return None
        payload = {
            "error": "Desktop activation required before Career Copilot Premium can be used on this computer.",
            "license_required": True,
            **current_license_status(),
        }
        if path.startswith("/api/") or _wants_json_response():
            return jsonify(payload), 403
        return render_template("activation.html", license_status=payload)

    @app.get("/")
    def root() -> Response | str:
        if not is_machine_licensed():
            return render_template("activation.html", license_status=current_license_status())
        if _has_existing_sessions():
            return redirect(url_for("dashboard"))
        return redirect(url_for("onboarding"))

    @app.get("/dashboard")
    def dashboard() -> str:
        active = _has_existing_sessions()
        return render_template(
            "index.html",
            session_online=active,
            session_status_label="Session Active" if active else "Session Offline",
        )

    @app.get("/settings")
    def settings_page() -> str:
        return render_template("settings.html")

    @app.get("/session/<session_id>/live")
    def live_session(session_id: str) -> Response | str:
        from mobile_app.live_bridge import build_live_bridge_payload_for_session

        try:
            payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
        except KeyError as error:
            return jsonify({"error": _display_error(error)}), 404

        return render_template(
            "live_session.html",
            session_id=session_id,
            initial_payload=payload,
            session_online=True,
            session_status_label="Session Live",
        )

    @app.route("/onboarding", methods=["GET", "POST"])
    def onboarding() -> Response | str:
        wants_json = (
            request.args.get("response_format") == "json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
        )

        if request.method == "GET":
            return render_template(
                "onboarding.html",
                session_online=False,
                session_status_label="No Active Session",
            )
        full_name = request.form.get("full_name", "").strip()
        target_name = request.form.get("target_name", "").strip()
        current_role = request.form.get("current_role", "").strip()
        resume_file = request.files.get("resume")
        product_description = request.form.get("product_description", "").strip()

        if not full_name or not target_name:
            if wants_json:
                return jsonify({"ok": False, "error": "Enter your name and target role."}), 400
            return _render_onboarding_error("Enter your name and target role.")

        resume_payload = _extract_onboarding_resume_payload(resume_file, product_description)
        if not resume_payload["text"]:
            if wants_json:
                return jsonify({"ok": False, "error": "Upload a resume PDF or type a product or service description."}), 400
            return _render_onboarding_error("Upload a resume PDF or type a product or service description.")

        try:
            profile_path = _materialize_onboarding_profile(
                full_name=full_name,
                current_role=current_role or target_name or "Professional",
                target_name=target_name,
                resume_text=resume_payload["text"],
                resume_filename=resume_payload["filename"],
                product_description=product_description,
            )
            session_id = _start_onboarding_session(profile_path.parent, target_name)
        except Exception as error:
            import traceback

            tb = traceback.format_exc()
            current_app.logger.error("Onboarding failed: %s\n%s", error, tb)
            if wants_json:
                return jsonify({"ok": False, "error": str(error)}), 500
            message = str(error).strip() or "Could not create session. Please retry."
            return _render_onboarding_error(message)

        if wants_json:
            response = jsonify(
                {
                    "ok": True,
                    "session_id": session_id,
                    "connect_mobile_url": "/dashboard#command-deck",
                    "dashboard_url": "/dashboard",
                    "bridge_hint": _bridge_base_url(),
                }
            )
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response, 200

        return redirect(url_for("dashboard"))

    @app.get("/api/license/status")
    def license_status() -> Response:
        return jsonify(current_license_status())

    @app.post("/api/license/activate")
    def license_activate() -> Response:
        body = request.get_json(silent=True) or {}
        activation_code = str(body.get("activation_code", "") or "")
        try:
            payload = activate_machine_license(activation_code)
        except ValueError as error:
            return jsonify({"error": str(error), **current_license_status()}), 400
        return jsonify(payload), 200

    @app.get("/api/system/preflight")
    def system_preflight() -> Response:
        from desktop_app.audio_handler import microphone_capture_status as audio_mic_status
        from runtime_paths import load_env_file

        load_env_file()
        microphone = audio_mic_status()
        license_ok = is_machine_licensed()
        ollama_ok = _probe_ollama_health()
        mistral_ok = bool(os.environ.get("MISTRAL_API_KEY", "").strip())
        ai_ready = ollama_ok or mistral_ok
        loopback_ok = bool(microphone.get("using_loopback"))
        can_go_live = bool(license_ok and microphone.get("can_capture") and ai_ready)
        checks = [
            {
                "id": "license",
                "label": "Desktop activation",
                "ok": license_ok,
                "hint": "Enter your activation code on first launch." if not license_ok else "Licensed for this computer.",
            },
            {
                "id": "microphone",
                "label": "Audio capture",
                "ok": bool(microphone.get("can_capture")),
                "hint": str(microphone.get("message", "Check Windows microphone permissions.")),
            },
            {
                "id": "loopback",
                "label": "Call audio (Stereo Mix)",
                "ok": loopback_ok,
                "hint": (
                    "Stereo Mix detected — Zoom/WhatsApp call audio can be captured."
                    if loopback_ok
                    else "Enable Stereo Mix in Windows Sound settings for call capture. See docs/requirements/STEREO-MIX-SETUP.txt"
                ),
            },
            {
                "id": "ollama",
                "label": "Ollama AI engine",
                "ok": ollama_ok,
                "hint": (
                    "Ollama is running locally."
                    if ollama_ok
                    else "Install Ollama and run: ollama pull llama3.2:1b — see docs/requirements/DOWNLOAD-OLLAMA.txt"
                ),
            },
            {
                "id": "mistral",
                "label": "Mistral API (optional fallback)",
                "ok": mistral_ok,
                "hint": (
                    "Mistral API key configured."
                    if mistral_ok
                    else "Optional: add MISTRAL_API_KEY to .env — see docs/requirements/DOWNLOAD-MISTRAL.txt"
                ),
            },
            {
                "id": "ai",
                "label": "AI answer engine ready",
                "ok": ai_ready,
                "hint": "Ollama or Mistral must be available to generate live answers.",
            },
        ]
        return jsonify(
            {
                "ok": True,
                "can_go_live": can_go_live,
                "checks": checks,
                "microphone": microphone,
                "license": current_license_status(),
            }
        )

    @app.get("/api/bridge/status")
    def bridge_status() -> Response:
        from mobile_app.live_bridge import mobile_connection_status

        bridge_url = _bridge_base_url()
        mobile = mobile_connection_status()
        return jsonify(
            {
                "ok": True,
                "bridge_url": bridge_url,
                "mobile_hint": "Enter this address in the mobile app if auto-discovery does not connect.",
                "pairing_ready": _has_existing_sessions(),
                "mobile_connected": bool(mobile.get("connected")),
                "mobile_last_seen": str(mobile.get("last_seen", "")),
                "mobile_session_id": str(mobile.get("session_id", "")),
            }
        )

    @app.get("/api/portable/status")
    def portable_status() -> Response:
        from runtime_paths import portable_status_payload

        return jsonify({"ok": True, **portable_status_payload()})

    @app.get("/api/sessions/recent")
    def recent_sessions() -> Response:
        try:
            entries = list(_load_recent_session_entries(_registry_path()).values())[:6]
            payload = []
            for entry in entries:
                payload.append(
                    {
                        "session_id": str(entry.get("session_id", "")),
                        "profile_name": str(entry.get("profile_name", "")),
                        "company_name": str(entry.get("company_name", "")),
                        "role_title": str(entry.get("role_title", "")),
                        "meeting_source": str(entry.get("meeting_source", "Manual / generic interview") or "Manual / generic interview"),
                        "worker_status": str(entry.get("worker_status", "stopped") or "stopped"),
                        "session_status": _normalize_session_status(str(entry.get("worker_status", "stopped") or "stopped")),
                        "updated_at": str(entry.get("updated_at", "")),
                    }
                )
            return jsonify({"sessions": payload})
        except PermissionError as error:
            return jsonify({"ok": False, "error": str(error)}), 403
        except Exception as error:
            current_app.logger.exception("Recent sessions failed")
            return jsonify({"ok": False, "error": str(error)}), 500

    @app.post("/api/sessions/cleanup")
    def sessions_cleanup() -> Response:
        """Delete sessions older than the requested threshold (default 24 hours)."""
        try:
            from desktop_app.runtime_controller import cleanup_sessions

            body = request.get_json(silent=True) or {}
            hours_old = int(body.get("hours_old", 24) or 24)
            message = cleanup_sessions(hours_old=max(1, hours_old), registry_path=_registry_path())
            return jsonify({"ok": True, "message": message}), 200
        except PermissionError as error:
            return jsonify({"ok": False, "error": str(error)}), 403
        except Exception as error:
            current_app.logger.exception("Session cleanup failed")
            return jsonify({"ok": False, "error": str(error)}), 500

    @app.post("/api/resume/extract")
    def resume_extract() -> Response:
        """Accept a resume file upload and return extracted text.

        Supports .txt (read directly), .pdf (via pdfminer if available),
        .doc/.docx (via python-docx if available).  Falls back to filename-only
        if the required library is not installed — the frontend handles that gracefully.
        """
        if "resume" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        resume_file = request.files["resume"]
        filename = resume_file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        text = ""
        skills_hint = ""

        try:
            if ext == "txt":
                text = resume_file.read().decode("utf-8", errors="replace")
            elif ext == "pdf":
                try:
                    from pdfminer.high_level import extract_text_to_fp  # type: ignore
                    from pdfminer.layout import LAParams  # type: ignore
                    import io
                    output = io.StringIO()
                    extract_text_to_fp(resume_file.stream, output, laparams=LAParams())
                    text = output.getvalue()
                except ImportError:
                    # pdfminer not installed — return empty text with filename
                    text = ""
            elif ext in ("doc", "docx"):
                try:
                    import docx  # type: ignore
                    import io
                    doc = docx.Document(io.BytesIO(resume_file.read()))
                    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                except ImportError:
                    text = ""
        except Exception as exc:
            return jsonify({"error": str(exc), "filename": filename, "text": ""}), 500

        return jsonify({"filename": filename, "text": text, "skills": skills_hint})

    @app.get("/api/briefing")
    def briefing_snapshot() -> Response:
        from .briefing import load_briefing

        payload = load_briefing(_briefing_storage_path(), DEFAULT_BRIEFING_ID)
        return jsonify({**payload, "microphone": _microphone_capture_status()})

    @app.post("/api/briefing")
    def briefing_save() -> Response:
        try:
            from desktop_app.runtime_controller import register_web_session
            from mobile_app.live_bridge import build_live_bridge_payload_for_session, ensure_live_session_worker
            from .briefing import build_operator_prompts, materialize_briefing_profile, save_briefing

            body = _trim_briefing_body(request.get_json(silent=True) or {})
            session_mode = str(body.get("session_mode", "progressive") or "progressive")
            microphone_status = microphone_capture_status()
            requested_microphone = body.get("use_microphone")
            if requested_microphone is None:
                prefer_microphone = bool(microphone_status.get("can_capture", False))
            else:
                prefer_microphone = _coerce_bool(requested_microphone) and bool(microphone_status.get("can_capture", False))
            briefing = save_briefing(_briefing_storage_path(), DEFAULT_BRIEFING_ID, dict(body))
            profile_path, profile_readiness, deferred_issues = materialize_briefing_profile(
                briefing,
                _profiles_root(),
                session_mode=session_mode,
            )
            briefing = save_briefing(
                _briefing_storage_path(),
                DEFAULT_BRIEFING_ID,
                {
                    **briefing,
                    "profile_path": str(profile_path),
                    "profile_readiness": profile_readiness,
                },
            )
            company_name = str(briefing.get("company_name", "")).strip() or "Target Company"
            role_title = str(briefing.get("target_role", "")).strip() or "Target Role"
            profile_name = str(briefing.get("full_name", "")).strip() or profile_path.parent.name
            operator_prompts = build_operator_prompts(briefing)
            session_id = register_web_session(
                profile_directory=profile_path.parent,
                company_name=company_name,
                role_title=role_title,
                profile_name=profile_name,
                registry_path=_registry_path(),
                prefer_microphone=prefer_microphone,
                operator_prompts=operator_prompts,
                extra_state={
                    "briefing_id": DEFAULT_BRIEFING_ID,
                    "meeting_source": str(briefing.get("meeting_source", "") or ""),
                    "meeting_capture_mode": str(briefing.get("meeting_capture_mode", "") or ""),
                    "meeting_window_name": str(briefing.get("meeting_window_name", "") or ""),
                    "camera_layout_preference": str(briefing.get("camera_layout_preference", "") or ""),
                    "briefing_company_values": str(briefing.get("company_values", "") or ""),
                    "briefing_expected_questions": str(briefing.get("expected_questions", "") or ""),
                },
            )
            try:
                worker_started = ensure_live_session_worker(session_id, _registry_path())
            except Exception as worker_error:
                current_app.logger.warning("Session worker skipped: %s", worker_error)
                worker_started = False
            session_payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
            return jsonify(
                {
                    "briefing": briefing,
                    "profile_path": briefing["profile_path"],
                    "profile_readiness": profile_readiness,
                    "deferred_issues": deferred_issues,
                    "session_id": session_id,
                    "profile_name": str(briefing.get("full_name", "")).strip() or profile_path.parent.name,
                    "company_name": company_name,
                    "role_name": role_title,
                    "microphone": microphone_status,
                    "worker_started": worker_started,
                    "session": session_payload,
                    "hint": "Press F2 or click Listen in the overlay to capture interviewer speech.",
                }
            ), 200
        except Exception as error:
            current_app.logger.exception("Briefing save failed")
            return jsonify({"error": str(error), "type": type(error).__name__}), 500

    @app.post("/api/session/quick-start")
    def session_quick_start() -> Response:
        """One-click session start using the latest saved profile and briefing."""
        try:
            from desktop_app.onboarding import is_session_ready
            from desktop_app.runtime_controller import register_web_session
            from mobile_app.live_bridge import build_live_bridge_payload_for_session, ensure_live_session_worker
            from .briefing import build_operator_prompts, load_briefing

            body = request.get_json(silent=True) or {}
            profile_directory = _resolve_quick_start_profile_directory(body)
            if profile_directory is None:
                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "No saved profile found. Complete onboarding once, "
                            "or upload your resume in the briefing wizard."
                        ),
                    }
                ), 400

            if not is_session_ready(profile_directory):
                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "Profile is incomplete. Open the briefing wizard, add your resume, "
                            "then click Resume Quick Start."
                        ),
                    }
                ), 400

            briefing = load_briefing(_briefing_storage_path(), DEFAULT_BRIEFING_ID)
            company_name = str(body.get("company_name") or briefing.get("company_name") or "").strip() or "Target Company"
            role_title = str(body.get("target_role") or briefing.get("target_role") or briefing.get("current_role") or "").strip() or "Target Role"
            microphone_status = microphone_capture_status()
            requested_microphone = body.get("use_microphone")
            if requested_microphone is None:
                prefer_microphone = bool(microphone_status.get("can_capture", False))
            else:
                prefer_microphone = _coerce_bool(requested_microphone) and bool(microphone_status.get("can_capture", False))

            profile_name = str(briefing.get("full_name", "")).strip() or profile_directory.name
            operator_prompts = build_operator_prompts(briefing)
            session_id = register_web_session(
                profile_directory=profile_directory,
                company_name=company_name,
                role_title=role_title,
                profile_name=profile_name,
                registry_path=_registry_path(),
                prefer_microphone=prefer_microphone,
                operator_prompts=operator_prompts,
                extra_state={
                    "briefing_id": DEFAULT_BRIEFING_ID,
                    "meeting_source": str(briefing.get("meeting_source", "Manual / generic interview") or "Manual / generic interview"),
                },
            )
            try:
                worker_started = ensure_live_session_worker(session_id, _registry_path())
            except Exception as worker_error:
                current_app.logger.warning("Session worker skipped: %s", worker_error)
                worker_started = False
            session_payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
            return jsonify(
                {
                    "ok": True,
                    "session_id": session_id,
                    "profile_directory": str(profile_directory),
                    "company_name": company_name,
                    "role_name": role_title,
                    "worker_started": worker_started,
                    "bridge_url": _bridge_base_url(),
                    "session": session_payload,
                    "hint": "Press F2 or click Listen in the overlay to capture the interviewer's question and generate your script.",
                    "microphone": microphone_status,
                }
            ), 200
        except PermissionError as error:
            return jsonify({"ok": False, "error": str(error)}), 403
        except Exception as error:
            current_app.logger.exception("Quick start failed")
            return jsonify({"ok": False, "error": str(error), "type": type(error).__name__}), 500

    @app.get("/api/session/<session_id>")
    def session_snapshot(session_id: str) -> Response:
        from mobile_app.live_bridge import build_live_bridge_payload_for_session

        try:
            payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
        except KeyError as error:
            return jsonify({"error": _display_error(error)}), 404
        return jsonify(payload)

    @app.post("/api/session/<session_id>/listen")
    def session_live_listen(session_id: str) -> Response:
        from desktop_app.language_config import save_language_prefs
        from desktop_app.live_listen import build_listening_state_for_session, run_live_listen_cycle

        body = request.get_json(silent=True) or {}
        try:
            listen_language = str(body.get("listen_language", "") or "").strip()
            reply_language = str(body.get("reply_language", "") or "").strip()
            if listen_language and reply_language:
                save_language_prefs(listen_language, reply_language)
            build_listening_state_for_session(session_id, _registry_path())
            result = run_live_listen_cycle(
                session_id,
                registry_path=_registry_path(),
                max_seconds=float(body.get("max_seconds", 12) or 12),
                listen_language=listen_language or None,
                reply_language=reply_language or None,
            )
            from mobile_app.live_bridge import build_live_bridge_payload_for_session

            session_payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
            return jsonify(
                {
                    "ok": True,
                    "session_id": session_id,
                    "transcript": result.transcript,
                    "suggested_answer": result.suggested_answer,
                    "alternatives": result.alternatives,
                    "provider_status": result.provider_status,
                    "audio_source": result.audio_source,
                    "session": session_payload,
                }
            ), 200
        except KeyError as error:
            return jsonify({"ok": False, "error": _display_error(error)}), 404
        except Exception as error:
            current_app.logger.exception("Live listen failed for session %s", session_id)
            return jsonify({"ok": False, "error": str(error), "type": type(error).__name__}), 500

    @app.post("/api/session/<session_id>/transcript")
    def session_transcript_answer(session_id: str) -> Response:
        from desktop_app.live_listen import run_live_listen_cycle
        from mobile_app.live_bridge import build_live_bridge_payload_for_session

        body = request.get_json(silent=True) or {}
        transcript = str(body.get("transcript", "") or "").strip()
        if not transcript:
            return jsonify({"ok": False, "error": "Transcript text is required."}), 400

        try:
            result = run_live_listen_cycle(
                session_id,
                registry_path=_registry_path(),
                transcript_text=transcript,
            )
            session_payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
            return jsonify(
                {
                    "ok": True,
                    "session_id": session_id,
                    "transcript": result.transcript,
                    "suggested_answer": result.suggested_answer,
                    "alternatives": result.alternatives,
                    "provider_status": result.provider_status,
                    "session": session_payload,
                }
            ), 200
        except KeyError as error:
            return jsonify({"ok": False, "error": _display_error(error)}), 404
        except Exception as error:
            current_app.logger.exception("Transcript answer failed for session %s", session_id)
            return jsonify({"ok": False, "error": str(error), "type": type(error).__name__}), 500

    @app.post("/api/session/<session_id>/actions/<action_id>")
    def session_action(session_id: str, action_id: str) -> Response:
        return _queue_session_action(session_id, action_id)

    @app.post("/session/<session_id>/actions/<action_id>")
    def session_action_live(session_id: str, action_id: str) -> Response:
        return _queue_session_action(session_id, action_id)

    @app.post("/api/session/<session_id>/prompts")
    def session_prompts(session_id: str) -> Response:
        from desktop_app.runtime_controller import update_registered_session_state
        from mobile_app.live_bridge import build_live_bridge_payload_for_session

        body = request.get_json(silent=True) or {}
        try:
            update_registered_session_state(
                session_id,
                {
                    "persistent_prompt": str(body.get("persistent_prompt", "") or ""),
                    "live_prompt": str(body.get("live_prompt", "") or ""),
                },
                registry_path=_registry_path(),
            )
            payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
        except KeyError as error:
            return jsonify({"error": _display_error(error)}), 404

        return jsonify(payload), 200

    @app.post("/api/pairing/create")
    def pairing_create() -> Response:
        from mobile_app.live_bridge import create_pairing_code, register_pairing_code

        try:
            payload = create_pairing_code(_registry_path())
            register_pairing_code(
                str(payload.get("pairing_code", "")),
                str(payload.get("session_id", "")),
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify(payload), 200

    @app.get("/api/pairing/qr/<code>")
    def pairing_qr(code: str) -> Response:
        """Return an inline SVG QR code for the given 6-digit pairing code.

        Uses only the Python standard library — no extra dependencies.
        The QR data encodes the deep-link URL that mobile clients can scan.
        """
        normalized = "".join(c for c in code if c.isdigit())[:6]
        if len(normalized) != 6:
            return jsonify({"error": "Invalid code"}), 400

        # Build a LAN-reachable bridge URL for the mobile APK rather than a
        # localhost dashboard URL that only works on the desktop itself.
        bridge_base = _pairing_bridge_base_url().rstrip("/")
        connect_url = (
            f"{bridge_base}/pairing/confirm"
            f"?pairingCode={normalized}"
            f"&bridgeUrl={quote(bridge_base, safe=':/')}"
        )

        try:
            import io
            import segno

            svg_buffer = io.StringIO()
            segno.make(connect_url, error="h").save(svg_buffer, kind="svg", scale=5, border=2)
            return Response(svg_buffer.getvalue(), mimetype="image/svg+xml")
        except Exception as error:
            current_app.logger.warning("Segno SVG QR generation failed, trying qrcode fallback: %s", error)

        try:
            import io

            qrcode_module = _load_qrcode_module()
            if qrcode_module is None:
                raise ImportError("qrcode is not installed")

            qr = qrcode_module.QRCode(error_correction=qrcode_module.constants.ERROR_CORRECT_H, box_size=10, border=4)
            qr.add_data(connect_url)
            qr.make(fit=True)

            # Prefer PNG output for compact payloads; fall back to the qrcode
            # SVG factory when Pillow is unavailable in frozen runtime bundles.
            try:
                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                from flask import send_file  # noqa: PLC0415

                return send_file(buf, mimetype="image/png")
            except Exception as error:
                current_app.logger.warning("PNG QR generation failed, trying SVG fallback: %s", error)
                from qrcode.image.svg import SvgImage  # noqa: PLC0415

                svg_img = qr.make_image(image_factory=SvgImage)
                svg_markup = svg_img.to_string(encoding="unicode")
                return Response(svg_markup, mimetype="image/svg+xml")
        except Exception as error:
            current_app.logger.warning("Real QR generation failed; using simple SVG fallback: %s", error)
            pass

        # Fallback: return SVG text QR built with a minimal pure-Python matrix.
        # This intentionally uses a simplified fixed pattern — sufficient for UI
        # display; the user can also just type the 6-digit code.
        svg = _build_simple_qr_svg(connect_url, normalized)
        return Response(svg, mimetype="image/svg+xml")

    @app.get("/mobile/connect")
    def mobile_connect() -> Response:
        code = "".join(character for character in request.args.get("code", "") if character.isdigit())[:6]
        bridge_url = str(request.args.get("bridgeUrl", "") or "").strip()
        return jsonify(
            {
                "ok": True,
                "pairing_code": code,
                "bridge_url": bridge_url,
                "message": "Open the Career Copilot mobile app and scan this QR or enter the code there.",
            }
        )

    @app.post("/api/pairing/confirm")
    def pairing_confirm() -> Response:
        from mobile_app.live_bridge import build_live_bridge_payload_for_session, confirm_pairing_code

        body = request.get_json(silent=True) or {}
        code = str(body.get("pairing_code", ""))
        try:
            payload = confirm_pairing_code(code, _registry_path())
            session_payload = build_live_bridge_payload_for_session(
                payload["session_id"],
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except KeyError as error:
            return jsonify({"error": _display_error(error)}), 404

        return jsonify({**payload, "session": session_payload}), 200

    @app.get("/api/session/<session_id>/events")
    def session_events(session_id: str) -> Response:
        from mobile_app.live_bridge import build_live_bridge_payload_for_session
        from .websocket import build_session_event, stream_session_events

        try:
            build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
        except KeyError as error:
            return jsonify({"error": _display_error(error)}), 404

        if request.args.get("once") == "1":
            return Response(
                build_session_event(
                    session_id,
                    registry_path=_registry_path(),
                    base_url=_bridge_base_url(),
                ),
                content_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        return Response(
            stream_with_context(
                stream_session_events(
                    session_id,
                    registry_path=_registry_path(),
                    base_url=_bridge_base_url(),
                )
            ),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


def _registry_path() -> Path:
    try:
        configured = current_app.config.get("SESSION_REGISTRY_PATH")
    except RuntimeError:
        configured = None
    path = Path(str(configured)) if configured else session_registry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        test_file = path.parent / ".write_test"
        test_file.touch()
        test_file.unlink()
        return path
    except (OSError, PermissionError):
        fallback = session_registry_path(_user_data_root())
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def _resolve_quick_start_profile_directory(body: dict[str, object]) -> Path | None:
    explicit = str(body.get("profile_directory", "") or "").strip()
    if explicit:
        candidate = Path(explicit)
        if candidate.is_dir():
            return candidate

    briefing = load_briefing_helper()
    briefing_path = str(briefing.get("profile_path", "") or "").strip()
    if briefing_path:
        candidate = Path(briefing_path).parent
        if candidate.is_dir():
            return candidate

    profiles_base = _profiles_root()
    if not profiles_base.exists():
        return None

    ready_dirs = sorted(
        [
            item
            for item in profiles_base.iterdir()
            if item.is_dir() and (item / "user_session_ready.flag").exists()
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return ready_dirs[0] if ready_dirs else None


def load_briefing_helper() -> dict[str, object]:
    from .briefing import load_briefing

    return load_briefing(_briefing_storage_path(), DEFAULT_BRIEFING_ID)


def _queue_session_action(session_id: str, action_id: str) -> Response:
    if action_id == "listen":
        from desktop_app.live_listen import build_listening_state_for_session, run_live_listen_cycle
        from mobile_app.live_bridge import build_live_bridge_payload_for_session

        try:
            build_listening_state_for_session(session_id, _registry_path())
            result = run_live_listen_cycle(session_id, registry_path=_registry_path())
            session_payload = build_live_bridge_payload_for_session(
                session_id,
                registry_path=_registry_path(),
                base_url=_bridge_base_url(),
            )
            return jsonify(
                {
                    "queued_action": action_id,
                    "session_id": session_id,
                    "status": "completed",
                    "transcript": result.transcript,
                    "suggested_answer": result.suggested_answer,
                    "session": session_payload,
                }
            ), 200
        except KeyError as error:
            return jsonify({"error": _display_error(error)}), 404
        except Exception as error:
            current_app.logger.exception("Queued live listen failed for session %s", session_id)
            return jsonify({"error": str(error), "type": type(error).__name__}), 500

    from mobile_app.live_bridge import ensure_live_session_worker
    from mobile_app.runtime_bridge import build_mobile_bridge_snapshot_for_session, enqueue_mobile_bridge_action

    try:
        worker_started = ensure_live_session_worker(session_id, _registry_path())
        snapshot = build_mobile_bridge_snapshot_for_session(session_id, _registry_path())
        queue_path = enqueue_mobile_bridge_action(snapshot, action_id, _registry_path())
    except KeyError as error:
        return jsonify({"error": _display_error(error)}), 404
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(
        {
            "queued_action": action_id,
            "queue_path": str(queue_path),
            "session_id": session_id,
            "status": "queued",
            "worker_started": worker_started,
        }
    ), 202


def _has_existing_sessions() -> bool:
    path = _registry_path()
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False

    for value in payload.values():
        if not isinstance(value, dict):
            continue
        profile_directory = str(value.get("profile_directory", "")).strip()
        if not profile_directory:
            continue
        try:
            if Path(profile_directory).exists():
                return True
        except OSError:
            continue
    return False


def _render_onboarding_error(message: str) -> tuple[str, int]:
    if _wants_json_response():
        return jsonify({"ok": False, "error": message}), 400

    return render_template(
        "onboarding.html",
        error_message=message,
        session_online=False,
        session_status_label="No Active Session",
    ), 400


def _wants_json_response() -> bool:
    response_format = str(request.args.get("response_format", "")).strip().lower()
    if response_format in {"json", "xhr", "1", "true"}:
        return True

    if request.headers.get("X-Requested-With", "") == "XMLHttpRequest":
        return True

    return "application/json" in str(request.headers.get("Accept", "")).lower()


def _extract_onboarding_resume_payload(resume_file, product_description: str) -> dict[str, str]:
    filename = ""
    extracted_text = ""
    if resume_file and getattr(resume_file, "filename", ""):
        filename = str(resume_file.filename or "").strip()
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        try:
            if ext == "pdf":
                try:
                    import io
                    from pdfminer.high_level import extract_text_to_fp  # type: ignore
                    from pdfminer.layout import LAParams  # type: ignore

                    output = io.StringIO()
                    extract_text_to_fp(resume_file.stream, output, laparams=LAParams())
                    extracted_text = output.getvalue().strip()
                except ImportError:
                    extracted_text = ""
            else:
                extracted_text = resume_file.read().decode("utf-8", errors="replace").strip()
        except Exception:
            extracted_text = ""

        if not extracted_text:
            extracted_text = f"Resume uploaded for {filename}."

    description = product_description.strip()
    if description:
        if extracted_text:
            extracted_text = f"{extracted_text}\n\nProduct or service description:\n{description}".strip()
        else:
            extracted_text = description

    if not filename:
        filename = "product-description.txt" if description else "resume.pdf"

    return {"filename": filename, "text": extracted_text}


def _materialize_onboarding_profile(
    *,
    full_name: str,
    current_role: str,
    target_name: str,
    resume_text: str,
    resume_filename: str,
    product_description: str,
) -> Path:
    profile_directory = _profiles_root() / _slug_profile_name(full_name)
    profile_directory.mkdir(parents=True, exist_ok=True)

    profile_payload = _build_onboarding_profile_payload(
        full_name=full_name,
        current_role=current_role,
        target_name=target_name,
        resume_text=resume_text,
        resume_filename=resume_filename,
        product_description=product_description,
    )

    profile_path = profile_directory / "user_complete_profile.json"
    profile_path.write_text(json.dumps(profile_payload, indent=2), encoding="utf-8")
    (profile_directory / "user_session_ready.flag").write_text("session-ready\n", encoding="utf-8")
    return profile_path


def _build_onboarding_profile_payload(
    *,
    full_name: str,
    current_role: str,
    target_name: str,
    resume_text: str,
    resume_filename: str,
    product_description: str,
) -> dict[str, object]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    project_summary = product_description.strip() or f"Session context for {target_name}."
    skill_names = [
        target_name,
        "Communication",
        "Problem Solving",
        "Positioning",
        "Discovery Calls",
        "Closing",
        "Client Strategy",
        "Offer Design",
        "Follow-up",
        "Execution",
    ]

    unique_skills: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in skill_names:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_skills.append(
            {
                "name": cleaned,
                "level": "Expert" if len(unique_skills) < 3 else "Intermediate",
            }
        )

    return {
        "identity": {
            "full_name": full_name,
            "current_role": current_role,
            "total_experience_years": 0,
            "location": "Remote",
            "work_mode": "Hybrid",
        },
        "skills": unique_skills,
        "work_history": [
            {
                "company_name": target_name,
                "duration": "Current focus",
                "achievements": [
                    "Prepared a launch-ready session profile.",
                    "Defined the core offer and conversation framing.",
                    "Started an operator session from the web onboarding flow.",
                ],
                "reason_for_leaving": "Active focus area.",
                "salary_expectations": "Open based on opportunity.",
            }
        ],
        "projects": [
            {
                "name": target_name,
                "description": project_summary,
                "technologies": ["Python", "Flask", "Local AI"],
                "contribution": product_description.strip() or f"Created the working session context for {target_name}.",
                "link": None,
            }
        ],
        "resume": {
            "filename": resume_filename,
            "extracted_text": resume_text,
            "confirmed": True,
            "source_format": "pdf" if resume_filename.lower().endswith(".pdf") else "text",
        },
        "weaknesses": {
            "english_fluency_level": 7,
            "technical_weak_areas": ["Live objections", "Conversation pressure"],
            "interview_anxiety_level": 4,
            "previous_interview_failures": "The operator should keep answers structured and calm under pressure.",
            "improvement_actions": [
                "Keep answers concise",
                "Anchor claims in proof points",
            ],
        },
        "target_job": {
            "job_title": target_name,
            "industry": "IT",
            "company_type": "Corporate",
            "interview_difficulty": "Senior",
        },
        "profile_version": "1.0",
        "created_at": now,
        "updated_at": now,
    }


def _slug_profile_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "candidate"


def _start_onboarding_session(profile_directory: Path, target_name: str) -> str:
    from desktop_app.runtime_controller import register_web_session

    return register_web_session(
        profile_directory=profile_directory,
        company_name=target_name,
        role_title=target_name,
        profile_name=target_name,
        registry_path=_registry_path(),
    )


def _trim_briefing_body(body: dict[str, object]) -> dict[str, object]:
    trimmed = dict(body)
    resume_text = str(trimmed.get("resume_text", "") or "")
    if len(resume_text) > 50000:
        trimmed["resume_text"] = resume_text[:50000]
    return trimmed


def _normalize_session_status(worker_status: str) -> str:
    normalized = str(worker_status or "").strip().casefold()
    if normalized in {"running", "active", "live", "listening", "armed"}:
        return "running"
    if normalized in {"new", "created", "starting"}:
        return "new"
    return "stopped"


def _load_recent_session_entries(registry_path: Path) -> dict[str, dict[str, object]]:
    from desktop_app.runtime_controller import load_registered_session_state, load_session_registry

    path = registry_path
    try:
        payload = load_session_registry(path)
    except OSError:
        payload = {}
    if not payload and path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    if isinstance(payload, dict):
        entries: dict[str, dict[str, object]] = {}
        for session_id, value in payload.items():
            if not isinstance(value, dict):
                continue
            merged_entry = dict(value)
            try:
                state_payload = load_registered_session_state(str(session_id), path)
            except KeyError:
                state_payload = {}
            if state_payload:
                merged_entry["meeting_source"] = str(
                    state_payload.get("meeting_source", merged_entry.get("meeting_source", "Manual / generic interview"))
                    or "Manual / generic interview"
                )
                merged_entry["updated_at"] = str(state_payload.get("updated_at", merged_entry.get("updated_at", "")) or merged_entry.get("updated_at", ""))
            entries[str(session_id)] = merged_entry
        return entries
    return {}


def _microphone_capture_status() -> dict[str, object]:
    global _MIC_RUNTIME_CACHE
    if _MIC_RUNTIME_CACHE is None:
        _MIC_RUNTIME_CACHE = _probe_microphone_runtime()
    return dict(_MIC_RUNTIME_CACHE)


microphone_capture_status = _microphone_capture_status


_OLLAMA_HEALTH_CACHE: dict[str, object] = {"at": 0.0, "ok": False}


def _probe_ollama_health() -> bool:
    import time
    import urllib.error
    import urllib.request

    age = time.time() - float(_OLLAMA_HEALTH_CACHE.get("at", 0.0))
    if age < 20.0:
        return bool(_OLLAMA_HEALTH_CACHE.get("ok", False))

    ok = False
    try:
        request_obj = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(request_obj, timeout=1.5) as response:
            ok = int(response.status) == 200
    except (OSError, TimeoutError, urllib.error.URLError, ValueError):
        ok = False
    _OLLAMA_HEALTH_CACHE["at"] = time.time()
    _OLLAMA_HEALTH_CACHE["ok"] = ok
    return ok


def _probe_microphone_runtime() -> dict[str, object]:
    input_devices: list[str] = []
    runtime_available = False
    try:
        import sounddevice as sd  # noqa: PLC0415

        sd.query_devices()
        runtime_available = True
        devices = sd.query_devices()
        input_devices = [
            str(device.get("name", "")).strip()
            for device in devices
            if int(device.get("max_input_channels", 0) or 0) > 0 and str(device.get("name", "")).strip()
        ]
    except Exception:
        runtime_available = False
        input_devices = []

    input_available = bool(input_devices)
    if not runtime_available:
        message = "Microphone support is not available in this install. Reinstall with audio drivers enabled."
    elif not input_available:
        message = "No recording device detected. Check Windows microphone permissions."
    else:
        message = "Live microphone capture is ready."

    return {
        "runtime_available": runtime_available,
        "input_available": input_available,
        "can_capture": runtime_available and input_available,
        "input_devices": input_devices,
        "message": message,
    }


def _load_qrcode_module():
    try:
        import qrcode
    except ImportError:
        return None
    return qrcode


def _bridge_base_url() -> str:
    configured = current_app.config.get("BRIDGE_BASE_URL")
    if configured:
        return str(configured).rstrip("/")
    return default_bridge_base_url()


def _pairing_bridge_base_url() -> str:
    return _bridge_base_url()


def _display_error(error: KeyError) -> str:
    if error.args:
        return str(error.args[0])
    return str(error)


def _extract_validation_issues(message: str) -> list[str]:
    prefix = "Cannot persist incomplete onboarding profile:"
    if not message.startswith(prefix):
        return []
    raw_issues = message[len(prefix) :].split(";")
    return [issue.strip() for issue in raw_issues if issue.strip()]


def _briefing_storage_path() -> Path:
    try:
        configured = current_app.config.get("BRIEFING_STORAGE_PATH")
    except RuntimeError:
        configured = None
    path = Path(str(configured)) if configured else briefing_storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _user_data_root() -> Path:
    """Return the user data directory for CareerCopilotPremium."""
    local_app_data = str(os.environ.get("LOCALAPPDATA", "")).strip()
    if local_app_data:
        return Path(local_app_data) / "CareerCopilotPremium"
    return Path.home() / "AppData" / "Local" / "CareerCopilotPremium"


def _profiles_root() -> Path:
    try:
        configured = current_app.config.get("BRIEFING_PROFILES_ROOT")
    except RuntimeError:
        configured = None
    
    # Try primary path first
    if configured:
        profile_root = Path(str(configured))
    else:
        profile_root = profiles_root()
    
    # Define fallback path
    fallback_root = _user_data_root() / "data" / "user_profiles"
    
    # Attempt to create and use primary path
    try:
        profile_root.mkdir(parents=True, exist_ok=True)
        # Verify write access
        test_file = profile_root / ".write_test"
        test_file.touch()
        test_file.unlink()
        return profile_root
    except (OSError, PermissionError):
        # Fallback to user data directory
        try:
            fallback_root.mkdir(parents=True, exist_ok=True)
            return fallback_root
        except (OSError, PermissionError) as e:
            raise OSError(f"Cannot create profile directory at {profile_root} or fallback {fallback_root}") from e


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _build_simple_qr_svg(url: str, code: str) -> str:
    """Return a minimal SVG that shows the 6-digit code prominently.

    Full QR matrix generation requires the `qrcode` library.  When that is
    not installed, we render a clear visual card instead — prominent 6-digit
    code plus instructions — which is enough for users to manually enter the
    code on their mobile device.
    """
    digits = " - ".join(list(code))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="260" height="200" viewBox="0 0 260 200">'
        '<rect width="260" height="200" rx="16" fill="#1a1d24"/>'
        '<rect x="10" y="10" width="240" height="180" rx="12" fill="#20242d" stroke="#2d3748" stroke-width="1"/>'
        '<text x="130" y="52" font-family="monospace" font-size="13" fill="#9ca3af" text-anchor="middle">Pairing Code</text>'
        f'<text x="130" y="102" font-family="monospace" font-size="36" font-weight="bold" fill="#3b82f6" text-anchor="middle" letter-spacing="6">{code}</text>'
        '<text x="130" y="136" font-family="monospace" font-size="11" fill="#6b7280" text-anchor="middle">Scan in mobile app or enter this code</text>'
        '<text x="130" y="160" font-family="monospace" font-size="10" fill="#4b5563" text-anchor="middle">Link Device stays available even without PNG QR support</text>'
        "</svg>"
    )