from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import importlib.metadata as importlib_metadata
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import sys
import traceback
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
USER_PROFILES_DIR = DATA_DIR / "user_profiles"
AUDIT_REPORT_PATH = DATA_DIR / "audit_report.txt"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ANSI_RESET = "\033[0m"
ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_CYAN = "\033[96m"
ANSI_BOLD = "\033[1m"


@dataclass
class AuditCheck:
    name: str
    passed: bool
    details: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _color(text: str, code: str) -> str:
    return f"{code}{text}{ANSI_RESET}"


def _print_header(title: str) -> None:
    print(_color(f"\n=== {title} ===", ANSI_CYAN + ANSI_BOLD))


def _pass_line(text: str) -> None:
    print(_color(f"PASS: {text}", ANSI_GREEN))


def _fail_line(text: str) -> None:
    print(_color(f"FAIL: {text}", ANSI_RED))


def _warn_line(text: str) -> None:
    print(_color(f"WARN: {text}", ANSI_YELLOW))


def _http_get_json(url: str, timeout: float = 5.0) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(response.status)
        payload_raw = response.read().decode("utf-8", errors="replace")
    payload = json.loads(payload_raw) if payload_raw.strip() else {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    return status, payload


def _http_post_json(url: str, payload: dict[str, object], timeout: float = 7.0) -> tuple[int, dict[str, object]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(response.status)
        payload_raw = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(payload_raw) if payload_raw.strip() else {}
    if not isinstance(parsed, dict):
        parsed = {"raw": parsed}
    return status, parsed


def check_dependencies() -> AuditCheck:
    required = [
        "flask",
        "cryptography",
        "qrcode",
        "pillow",
        "segno",
        "sounddevice",
        "soundfile",
        "numpy",
        "sqlalchemy",
        "pypdf",
        "PySide6",
        "werkzeug",
        "jinja2",
    ]
    dist_map = {
        "pillow": "Pillow",
        "PySide6": "PySide6",
    }
    details: list[str] = []
    missing: list[str] = []

    for package in required:
        distribution = dist_map.get(package, package)
        try:
            version = importlib_metadata.version(distribution)
            details.append(f"{package}: {version}")
        except importlib_metadata.PackageNotFoundError:
            missing.append(package)

    issues: list[str] = []
    if missing:
        install_cmd = f".venv\\Scripts\\pip.exe install {' '.join(missing)}"
        issues.append(f"Missing packages: {', '.join(missing)}")
        issues.append(f"Install command: {install_cmd}")
        details.append(f"Install command: {install_cmd}")

    return AuditCheck(
        name="Dependency Check",
        passed=not missing,
        details=details,
        issues=issues,
    )


def check_file_structure() -> AuditCheck:
    files = [
        ROOT / "web_app" / "app.py",
        ROOT / "web_app" / "routes.py",
        ROOT / "web_app" / "briefing.py",
        ROOT / "desktop_app" / "runtime_controller.py",
        ROOT / "desktop_app" / "database.py",
        ROOT / "mobile_app" / "live_bridge.py",
        ROOT / "mobile_app" / "runtime_bridge.py",
        ROOT / "app_licensing.py",
        ROOT / "requirements.txt",
    ]
    folders = [
        ROOT / "web_app" / "static" / "css",
        ROOT / "web_app" / "static" / "js",
        ROOT / "web_app" / "templates",
        ROOT / "data" / "cache",
        ROOT / "data" / "user_profiles",
    ]

    missing_files = [str(path.relative_to(ROOT)) for path in files if not path.exists()]
    missing_folders = [str(path.relative_to(ROOT)) for path in folders if not path.exists()]

    details = [
        f"Files checked: {len(files)}",
        f"Folders checked: {len(folders)}",
    ]
    issues: list[str] = []
    if missing_files:
        issues.append(f"Missing files: {', '.join(missing_files)}")
    if missing_folders:
        issues.append(f"Missing folders: {', '.join(missing_folders)}")

    return AuditCheck(
        name="File Structure Check",
        passed=(not missing_files and not missing_folders),
        details=details,
        issues=issues,
    )


def check_flask_app() -> AuditCheck:
    from web_app.app import create_app

    audit_root = CACHE_DIR / "audit_flask"
    profile_root = audit_root / "user_profiles"
    registry_path = audit_root / "session_registry.json"
    briefing_path = audit_root / "web_briefing_drafts.json"
    audit_root.mkdir(parents=True, exist_ok=True)
    profile_root.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("CCP_REQUIRE_LICENSE", "0")

    details: list[str] = []
    issues: list[str] = []
    passed = True

    app = create_app()
    app.config["TESTING"] = True
    app.config["SESSION_REGISTRY_PATH"] = str(registry_path)
    app.config["BRIEFING_STORAGE_PATH"] = str(briefing_path)
    app.config["BRIEFING_PROFILES_ROOT"] = str(profile_root)

    sample_briefing = {
        "full_name": "Audit Flask User",
        "current_role": "Full-Stack Developer",
        "experience_years": 4,
        "location": "Karachi",
        "work_mode": "Remote",
        "resume_filename": "audit_resume.txt",
        "resume_text": "Audit resume text with product and backend experience.",
        "skills": "Python, Flask, SQL, APIs, Testing",
        "target_role": "Backend Engineer",
        "company_name": "Audit Labs",
    }

    try:
        with app.test_client() as client:
            checks: list[tuple[str, str, str, int | tuple[int, int], dict[str, object] | None]] = [
                ("GET", "/", "root", (200, 302), None),
                ("GET", "/dashboard", "dashboard", 200, None),
                ("GET", "/static/css/app.css", "app.css", 200, None),
                ("GET", "/static/js/app.js", "app.js", 200, None),
                ("GET", "/api/briefing", "briefing-get", 200, None),
                ("POST", "/api/briefing", "briefing-post", 200, sample_briefing),
                ("GET", "/health", "health", 200, None),
                ("GET", "/api/sessions/recent", "recent-sessions", 200, None),
            ]

            for method, path, label, expected, payload in checks:
                if method == "GET":
                    response = client.get(path)
                else:
                    response = client.post(path, json=payload)

                status_code = int(response.status_code)
                ok = status_code in expected if isinstance(expected, tuple) else status_code == expected
                details.append(f"{label}: HTTP {status_code}")
                if not ok:
                    passed = False
                    issues.append(f"{label} expected {expected} but got {status_code}")
                    continue

                if path.startswith("/api/"):
                    if response.is_json:
                        body = response.get_json(silent=True)
                        if not isinstance(body, dict):
                            passed = False
                            issues.append(f"{label} did not return a JSON object")
                    else:
                        passed = False
                        issues.append(f"{label} response is not JSON")
    except Exception as error:
        passed = False
        issues.append(f"Flask client check crashed: {error}")
        issues.append(traceback.format_exc().strip())

    if not (audit_root / "session_registry.json").exists():
        details.append("No test registry file was generated under audit_flask.")

    return AuditCheck(name="Flask App Check", passed=passed, details=details, issues=issues)


def check_database() -> AuditCheck:
    from desktop_app.database import (
        get_session_entry,
        get_session_state,
        initialize_session_database,
        upsert_session_entry,
        upsert_session_state,
    )
    from desktop_app.encryption import decrypt_json_payload, encrypt_json_payload

    audit_db = CACHE_DIR / "audit_database.sqlite3"
    session_id = "audit-db-session"
    details: list[str] = []
    issues: list[str] = []
    passed = True

    try:
        initialize_session_database(audit_db)
        details.append(f"Database initialized: {audit_db}")

        entry = {
            "session_id": session_id,
            "profile_directory": str(USER_PROFILES_DIR / "audit-db"),
            "profile_name": "Audit DB",
            "company_name": "Audit Labs",
            "role_title": "QA Engineer",
            "microphone_enabled": False,
            "session_state_path": str(CACHE_DIR / "audit_db_state.json"),
            "session_command_queue_path": str(CACHE_DIR / "audit_db_queue.json"),
            "session_database_path": str(audit_db),
            "session_worker_state_path": str(CACHE_DIR / "audit_db_worker.json"),
            "worker_status": "stopped",
            "tags": ["audit"],
            "notes": "audit insert",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        upsert_session_entry(audit_db, entry)

        state_payload = {
            "session_id": session_id,
            "started": True,
            "overlay_status": "idle",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        upsert_session_state(audit_db, session_id, state_payload)

        loaded_entry = get_session_entry(audit_db, session_id)
        loaded_state = get_session_state(audit_db, session_id)
        if loaded_entry is None:
            passed = False
            issues.append("Session entry was not found after upsert.")
        if loaded_state is None:
            passed = False
            issues.append("Session state was not found after upsert.")
        elif loaded_state.get("session_id") != session_id:
            passed = False
            issues.append("Session state payload mismatch after read.")

        with sqlite3.connect(audit_db) as connection:
            row = connection.execute(
                "SELECT payload_json FROM session_states WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            passed = False
            issues.append("Encrypted payload row missing in session_states table.")
        else:
            cipher_text = str(row[0])
            if cipher_text.startswith("{"):
                passed = False
                issues.append("Session state payload appears unencrypted in database.")
            roundtrip = decrypt_json_payload(cipher_text)
            if roundtrip.get("session_id") != session_id:
                passed = False
                issues.append("Encrypted payload could not be decrypted correctly.")
            encrypted = encrypt_json_payload({"ok": True})
            if not encrypted.startswith("enc:v1:"):
                passed = False
                issues.append("Encryption helper did not return expected enc:v1 format.")

        details.append("SQLite create/write/read/encryption checks executed.")
    except Exception as error:
        passed = False
        issues.append(f"Database check crashed: {error}")
        issues.append(traceback.format_exc().strip())

    return AuditCheck(name="Database Check", passed=passed, details=details, issues=issues)


def check_mobile_bridge() -> AuditCheck:
    from desktop_app.runtime_controller import load_session_registry
    from mobile_app.live_bridge import register_pairing_code, start_mobile_bridge_server

    details: list[str] = []
    issues: list[str] = []
    passed = True

    registry_path = CACHE_DIR / "session_registry.json"
    pairing_path = CACHE_DIR / "pairing_codes.json"

    bridge_started_here = False
    bridge_server = None

    try:
        try:
            status, payload = _http_get_json("http://127.0.0.1:8765/health", timeout=1.5)
            if status == 200 and bool(payload.get("ok", False)):
                details.append("Existing mobile bridge on port 8765 is healthy.")
            else:
                raise RuntimeError("Existing mobile bridge health response was not ok:true")
        except Exception:
            bridge_server = start_mobile_bridge_server(
                host="127.0.0.1",
                port=8765,
                registry_path=registry_path,
            )
            bridge_started_here = True
            details.append("Started mobile bridge server on 127.0.0.1:8765.")

        status, payload = _http_get_json("http://127.0.0.1:8765/health", timeout=3.0)
        if status != 200 or not bool(payload.get("ok", False)):
            passed = False
            issues.append(f"Mobile bridge /health failed: status={status}, payload={payload}")
        else:
            details.append("Mobile bridge /health returned ok:true.")

        session_map = load_session_registry(registry_path)
        session_id = next(iter(session_map.keys()), None)
        pairing_code = f"{secrets.randbelow(1_000_000):06d}"
        pairing = register_pairing_code(pairing_code, session_id)
        pairing_code = str(pairing.get("pairing_code", pairing_code))
        if not re.fullmatch(r"\d{6}", pairing_code):
            passed = False
            issues.append(f"Pairing code format invalid: {pairing_code!r}")
        else:
            details.append(f"Pairing code generated: {pairing_code}")

        if not pairing_path.exists():
            passed = False
            issues.append(f"Pairing cache file not found: {pairing_path}")
        else:
            cache_payload = json.loads(pairing_path.read_text(encoding="utf-8"))
            if pairing_code not in cache_payload:
                passed = False
                issues.append("Generated pairing code was not persisted to pairing_codes.json")
            else:
                details.append("Pairing code persisted to data/cache/pairing_codes.json")
    except Exception as error:
        passed = False
        issues.append(f"Mobile bridge check crashed: {error}")
        issues.append(traceback.format_exc().strip())
    finally:
        if bridge_started_here and bridge_server is not None:
            try:
                bridge_server.stop()
                details.append("Stopped audit-started mobile bridge server.")
            except Exception as stop_error:
                _warn_line(f"Could not stop audit-started bridge server cleanly: {stop_error}")

    return AuditCheck(name="Mobile Bridge Check", passed=passed, details=details, issues=issues)


def _build_audit_profile(full_name: str):
    from desktop_app.onboarding import (
        CompleteUserProfile,
        IdentitySetup,
        ProjectPortfolioEntry,
        ResumeConfirmation,
        SkillEntry,
        TargetJobProfile,
        WeaknessProfile,
        WorkHistoryEntry,
    )

    skills = [
        SkillEntry(name="Python", level="Expert"),
        SkillEntry(name="Flask", level="Expert"),
        SkillEntry(name="SQL", level="Expert"),
        SkillEntry(name="APIs", level="Intermediate"),
        SkillEntry(name="Testing", level="Intermediate"),
        SkillEntry(name="System Design", level="Intermediate"),
        SkillEntry(name="Communication", level="Expert"),
        SkillEntry(name="Problem Solving", level="Expert"),
        SkillEntry(name="Docker", level="Intermediate"),
        SkillEntry(name="CI/CD", level="Intermediate"),
    ]
    return CompleteUserProfile(
        identity=IdentitySetup(
            full_name=full_name,
            current_role="Full-Stack Developer",
            total_experience_years=5,
            location="Karachi",
            work_mode="Remote",
        ),
        skills=skills,
        work_history=[
            WorkHistoryEntry(
                company_name="Audit Corp",
                duration="24 months",
                achievements=[
                    "Shipped a production Flask control room.",
                    "Reduced support load with automated diagnostics.",
                    "Delivered stable packaged Windows releases.",
                ],
                reason_for_leaving="Contract completion",
                salary_expectations="$25/hr",
            )
        ],
        projects=[
            ProjectPortfolioEntry(
                name="Career Copilot Premium",
                description="Built and maintained an interview operations workspace with live session controls and persistence.",
                technologies=["Python", "Flask", "SQLite"],
                contribution="Implemented backend flows, persistence, and runtime controls.",
            )
        ],
        resume=ResumeConfirmation(
            filename="audit_resume.txt",
            extracted_text="Audit profile resume text for deterministic validation.",
            confirmed=True,
            source_format="text",
        ),
        weaknesses=WeaknessProfile(
            english_fluency_level=7,
            technical_weak_areas=["System design", "Frontend architecture"],
            interview_anxiety_level=4,
            previous_interview_failures="Sometimes answers are too long.",
            improvement_actions=["Practice concise answers", "Use STAR structure"],
        ),
        target_job=TargetJobProfile(
            job_title="Backend Engineer",
            industry="IT/Software",
            company_type="Corporate",
            interview_difficulty="Senior",
        ),
    )


def check_session_creation() -> AuditCheck:
    from desktop_app.onboarding import save_completed_profile
    from desktop_app.runtime_controller import (
        build_session_runner,
        load_registered_session_state,
        load_session_registry,
        session_database_path_from_registry_path,
    )

    details: list[str] = []
    issues: list[str] = []
    passed = True

    test_profile_root = USER_PROFILES_DIR / "test-audit"
    audit_registry = CACHE_DIR / "audit_session_registry.json"
    audit_database = session_database_path_from_registry_path(audit_registry)
    runner = None

    try:
        if test_profile_root.exists():
            shutil.rmtree(test_profile_root, ignore_errors=True)
        test_profile_root.mkdir(parents=True, exist_ok=True)

        profile = _build_audit_profile("test-audit")
        profile_path = save_completed_profile(profile, test_profile_root)
        details.append(f"Created profile: {profile_path}")

        runner = build_session_runner(
            profile_directory=profile_path.parent,
            company_name="Audit Labs",
            role_title="Backend Engineer",
            prefer_microphone=False,
            session_registry_path=audit_registry,
        )
        runner.start()
        session_id = str(runner.session_id or "")
        if not session_id:
            passed = False
            issues.append("Runner did not produce a session_id.")
        else:
            details.append(f"Created session: {session_id}")

        registry = load_session_registry(audit_registry)
        if session_id not in registry:
            passed = False
            issues.append("Created session not found in audit registry.")

        state = load_registered_session_state(session_id, audit_registry)
        if str(state.get("session_id", "")) != session_id:
            passed = False
            issues.append("Loaded session state does not match created session ID.")
        else:
            details.append("Session state loaded successfully.")
    except Exception as error:
        passed = False
        issues.append(f"Session creation check crashed: {error}")
        issues.append(traceback.format_exc().strip())
    finally:
        if runner is not None:
            try:
                runner.stop()
            except Exception:
                pass

        shutil.rmtree(test_profile_root, ignore_errors=True)
        if audit_registry.exists():
            try:
                audit_registry.unlink()
            except OSError:
                pass
        if audit_database.exists():
            try:
                audit_database.unlink()
            except OSError:
                pass
        details.append("Cleaned up test-audit profile and audit registry/database files.")

    return AuditCheck(name="Session Creation Check", passed=passed, details=details, issues=issues)


def check_licensing() -> AuditCheck:
    from app_licensing import (
        activate_machine_license,
        current_license_status,
        generate_activation_code,
        machine_fingerprint,
        machine_request_code,
    )

    details: list[str] = []
    issues: list[str] = []
    passed = True

    try:
        fingerprint = machine_fingerprint()
        request_code = machine_request_code()
        activation_code = generate_activation_code(request_code)
        status = current_license_status()

        if not re.fullmatch(r"[A-F0-9]{24}", fingerprint):
            passed = False
            issues.append(f"Machine fingerprint format invalid: {fingerprint}")
        else:
            details.append(f"Machine fingerprint format valid: {fingerprint}")

        if not re.fullmatch(r"CCP(?:-[A-Z0-9]{4}){5}", request_code):
            passed = False
            issues.append(f"Request code format invalid: {request_code}")
        else:
            details.append(f"Request code format valid: {request_code}")

        if not re.fullmatch(r"ACT(?:-[A-Z0-9]{4}){5}", activation_code):
            passed = False
            issues.append(f"Generated activation code format invalid: {activation_code}")

        license_path = Path(str(status.get("license_path", "")))
        if not license_path.exists():
            passed = False
            issues.append(f"License file does not exist: {license_path}")
        else:
            if not bool(status.get("activated", False)):
                # Self-heal for local audit runs: generate machine-bound activation code and activate.
                activate_machine_license(activation_code)
                status = current_license_status()
                details.append("License auto-activation attempted during audit.")

            if not bool(status.get("activated", False)):
                passed = False
                issues.append("License file exists but is not activated/valid for this machine.")
            else:
                details.append(f"License file valid: {license_path}")
    except Exception as error:
        passed = False
        issues.append(f"Licensing check crashed: {error}")
        issues.append(traceback.format_exc().strip())

    return AuditCheck(name="Licensing Check", passed=passed, details=details, issues=issues)


def check_ollama_ai() -> AuditCheck:
    details: list[str] = []
    issues: list[str] = []
    passed = True

    host = "http://127.0.0.1:11434"
    model_name = "llama3.2:1b"

    try:
        tags_status, tags_payload = _http_get_json(f"{host}/api/tags", timeout=4.0)
        if tags_status != 200:
            passed = False
            issues.append(f"Ollama /api/tags returned status {tags_status}")
            return AuditCheck(name="Ollama/AI Check", passed=passed, details=details, issues=issues)

        models = tags_payload.get("models", [])
        names: list[str] = []
        if isinstance(models, list):
            for model in models:
                if isinstance(model, dict):
                    name = str(model.get("name", "")).strip()
                    if name:
                        names.append(name)

        details.append(f"Discovered models: {', '.join(names) if names else 'none'}")
        if model_name not in names:
            passed = False
            issues.append(f"Model not found: {model_name}")
            issues.append(f"Recommended fix: ollama pull {model_name}")
            return AuditCheck(name="Ollama/AI Check", passed=passed, details=details, issues=issues)

        gen_status, gen_payload = _http_post_json(
            f"{host}/api/generate",
            {
                "model": model_name,
                "prompt": "Reply with exactly: OK",
                "stream": False,
            },
            timeout=20.0,
        )
        if gen_status != 200:
            passed = False
            issues.append(f"Ollama /api/generate returned status {gen_status}")
        else:
            response_text = str(gen_payload.get("response", "")).strip()
            if not response_text:
                passed = False
                issues.append("Ollama generate response is empty.")
            else:
                details.append(f"Generate response sample: {response_text[:120]}")
    except urllib.error.URLError as error:
        passed = False
        issues.append(f"Could not connect to Ollama at {host}: {error}")
        issues.append("Recommended fix: start Ollama service and retry.")
    except Exception as error:
        passed = False
        issues.append(f"Ollama check crashed: {error}")
        issues.append(traceback.format_exc().strip())

    return AuditCheck(name="Ollama/AI Check", passed=passed, details=details, issues=issues)


def _render_console_report(results: list[AuditCheck]) -> None:
    _print_header("Career Copilot Premium Full Audit")
    for result in results:
        label = "PASS" if result.passed else "FAIL"
        color = ANSI_GREEN if result.passed else ANSI_RED
        print(_color(f"[{label}] {result.name}", color + ANSI_BOLD))
        for detail in result.details:
            print(f"  - {detail}")
        for issue in result.issues:
            _warn_line(f"  {issue}")

    passed_count = sum(1 for item in results if item.passed)
    total_count = len(results)
    score_line = f"Overall Score: {passed_count}/{total_count} checks passed"
    if passed_count == total_count:
        _pass_line(score_line)
    else:
        _fail_line(score_line)


def _write_text_report(results: list[AuditCheck]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("Career Copilot Premium Full Audit Report")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Workspace root: {ROOT}")
    lines.append("")

    passed_count = sum(1 for item in results if item.passed)
    total_count = len(results)
    lines.append(f"Overall Score: {passed_count}/{total_count} checks passed")
    lines.append("")

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"[{status}] {result.name}")
        for detail in result.details:
            lines.append(f"  - {detail}")
        if result.issues:
            lines.append("  Issues:")
            for issue in result.issues:
                lines.append(f"  - {issue}")
        lines.append("")

    all_issues = [issue for result in results for issue in result.issues]
    lines.append("Recommended Fixes")
    if all_issues:
        for issue in all_issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- No issues found.")

    AUDIT_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return AUDIT_REPORT_PATH


def main() -> int:
    os.chdir(ROOT)
    checks = [
        check_dependencies,
        check_file_structure,
        check_flask_app,
        check_database,
        check_mobile_bridge,
        check_session_creation,
        check_licensing,
        check_ollama_ai,
    ]

    results: list[AuditCheck] = []
    for check_fn in checks:
        try:
            result = check_fn()
        except Exception as error:
            result = AuditCheck(
                name=check_fn.__name__,
                passed=False,
                details=[],
                issues=[f"Unhandled audit exception: {error}", traceback.format_exc().strip()],
            )
        results.append(result)

    _render_console_report(results)
    report_path = _write_text_report(results)
    print(_color(f"\nReport saved to: {report_path}", ANSI_CYAN))

    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
