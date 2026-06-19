"""Command-line entrypoint for the packaged desktop baseline."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback
import urllib.error
import urllib.request
import webbrowser
from typing import TYPE_CHECKING

from .config_manager import RuntimeConfig, load_runtime_config

if TYPE_CHECKING:
    from .answer_builder import AnswerEngine
    from .stt_engine import STTEngine


_PACKAGED_PREVIEW_MUTEX_HANDLE = None
_PACKAGED_PREVIEW_MUTEX_NAME = "CareerCopilotPremiumControlRoom"


@dataclass
class DesktopRuntime:
    runtime_config: RuntimeConfig
    stt_engine: STTEngine
    answer_engine: AnswerEngine


def build_desktop_runtime(config_dir: Path | None = None) -> DesktopRuntime:
    from .answer_builder import build_answer_engine
    from .stt_engine import build_stt_engine

    runtime_config = load_runtime_config(config_dir)
    stt_engine = build_stt_engine(runtime_config.model)
    answer_engine = build_answer_engine(runtime_config.model)
    return DesktopRuntime(runtime_config=runtime_config, stt_engine=stt_engine, answer_engine=answer_engine)


def apply_runtime_overrides(
    runtime: DesktopRuntime,
    llm_base_url: str | None = None,
    llm_timeout_seconds: float | None = None,
) -> DesktopRuntime:
    from .answer_builder import build_answer_engine

    if llm_base_url is not None:
        runtime.runtime_config.model.llm_base_url = llm_base_url
    if llm_timeout_seconds is not None:
        runtime.runtime_config.model.llm_timeout_seconds = llm_timeout_seconds
    runtime.answer_engine = build_answer_engine(runtime.runtime_config.model)
    return runtime


def build_runtime_summary(runtime: DesktopRuntime) -> str:
    runtime_config = runtime.runtime_config
    return (
        "Career Copilot Premium\n"
        f"Theme: {runtime_config.app.theme}\n"
        f"Hotkey: {runtime_config.app.hotkey}\n"
        f"Overlay opacity: {runtime_config.app.overlay_opacity}\n"
        f"STT model: {runtime_config.model.stt_model}\n"
        f"STT engine: {type(runtime.stt_engine).__name__}\n"
        f"LLM model: {runtime_config.model.llm_model}\n"
        f"LLM endpoint: {runtime_config.model.llm_base_url}\n"
        f"LLM timeout: {runtime_config.model.llm_timeout_seconds}\n"
        f"Answer engine: {type(runtime.answer_engine).__name__}\n"
        f"Premium features: {', '.join(runtime_config.premium.features)}"
    )


def should_launch_packaged_preview(argv: list[str] | None) -> bool:
    if not getattr(sys, "frozen", False):
        return False

    effective_argv = sys.argv[1:] if argv is None else argv
    return len(effective_argv) == 0


def resolve_dashboard_port(host: str = "127.0.0.1", preferred_port: int = 5000) -> int:
    for port in range(preferred_port, preferred_port + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
        return port
    raise RuntimeError("Could not find an available port for the Career Copilot control room.")


def default_session_registry_path() -> Path:
    from runtime_paths import session_registry_path

    return session_registry_path()


def find_existing_dashboard_url(host: str = "127.0.0.1", preferred_port: int = 5000) -> str | None:
    for port in range(preferred_port, preferred_port + 25):
        url = f"http://{host}:{port}/api/health"
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status != 200:
                    continue
                payload = response.read().decode("utf-8", errors="ignore")
                if '"ok":true' in payload.replace(" ", ""):
                    return f"http://{host}:{port}"
        except (OSError, TimeoutError, urllib.error.URLError):
            continue
    return None


def wait_for_existing_dashboard_url(host: str = "127.0.0.1", preferred_port: int = 5000, attempts: int = 20) -> str | None:
    for _ in range(attempts):
        existing_url = find_existing_dashboard_url(host=host, preferred_port=preferred_port)
        if existing_url is not None:
            return existing_url
        try:
            ctypes.windll.kernel32.Sleep(250)
        except Exception:
            pass
    return None


def resolve_mobile_bridge_public_host() -> str:
    candidates: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            candidates.append(str(probe.getsockname()[0]))
    except OSError:
        pass

    try:
        hostname_candidates = socket.gethostbyname_ex(socket.gethostname())[2]
        candidates.extend(str(item) for item in hostname_candidates)
    except OSError:
        pass

    for candidate in candidates:
        if candidate.startswith("127.") or candidate.startswith("169.254."):
            continue
        return candidate

    return "127.0.0.1"


def is_mobile_bridge_healthy(host: str = "127.0.0.1", port: int = 8765) -> bool:
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            if response.status != 200:
                return False
            payload = response.read().decode("utf-8", errors="ignore")
            return '"ok": true' in payload or '"ok":true' in payload.replace(" ", "")
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def acquire_packaged_preview_mutex() -> bool:
    global _PACKAGED_PREVIEW_MUTEX_HANDLE

    if os.name != "nt":
        return True

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, _PACKAGED_PREVIEW_MUTEX_NAME)
    if not handle:
        return True

    _PACKAGED_PREVIEW_MUTEX_HANDLE = handle
    already_exists = ctypes.windll.kernel32.GetLastError() == 183
    return not already_exists


def open_dashboard_in_browser(url: str) -> None:
    chrome_candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in chrome_candidates:
        if candidate.exists():
            subprocess.Popen([str(candidate), url])
            return

    webbrowser.open(url)


def launch_web_dashboard(
    registry_path: Path | None = None,
    host: str = "127.0.0.1",
    preferred_port: int = 5000,
    open_browser: bool = True,
) -> int:
    from werkzeug.serving import make_server

    from mobile_app.live_bridge import start_mobile_bridge_server
    from web_app.app import create_app

    from runtime_paths import configure_runtime_environment, default_bridge_base_url, session_registry_path

    configure_runtime_environment()
    resolved_registry_path = registry_path or session_registry_path()
    existing_url = find_existing_dashboard_url(host=host, preferred_port=preferred_port)
    if existing_url is not None and is_mobile_bridge_healthy(host="127.0.0.1", port=8765):
        if open_browser:
            open_dashboard_in_browser(existing_url)
        return 0

    port = resolve_dashboard_port(host=host, preferred_port=preferred_port)
    bridge_base = default_bridge_base_url()
    bridge_server = None
    if not is_mobile_bridge_healthy(host="127.0.0.1", port=8765):
        try:
            bridge_server = start_mobile_bridge_server(
                host="0.0.0.0",
                port=8765,
                registry_path=resolved_registry_path,
            )
            os.environ["BRIDGE_BASE_URL"] = bridge_server.url
            bridge_base = bridge_server.url
        except OSError:
            bridge_server = None

    app = create_app()
    app.config["SESSION_REGISTRY_PATH"] = str(resolved_registry_path)
    app.config["BRIDGE_BASE_URL"] = os.environ.get("BRIDGE_BASE_URL", "").strip() or bridge_base
    url = f"http://{host}:{port}"

    server = make_server(host, port, app, threaded=True)
    if open_browser:
        open_dashboard_in_browser(url)

    try:
        server.serve_forever()
    finally:
        server.server_close()
        if bridge_server is not None:
            bridge_server.stop()


def write_startup_error_log(error: BaseException) -> Path:
    if getattr(sys, "frozen", False):
        log_root = Path(sys.executable).resolve().parent / "logs"
    else:
        log_root = Path.cwd() / "logs"

    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / "startup-error.log"
    log_path.write_text(traceback.format_exc(), encoding="utf-8")
    return log_path


def show_packaged_error_dialog(message: str) -> None:
    if not getattr(sys, "frozen", False):
        return

    try:
        ctypes.windll.user32.MessageBoxW(None, message, "Career Copilot Startup Error", 0x10)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Career Copilot Premium desktop baseline")
    parser.add_argument("--config-dir", type=Path, default=None, help="Optional config directory override")
    parser.add_argument("--gui-preview", action="store_true", help="Launch the optional desktop overlay and settings preview")
    parser.add_argument("--web-dashboard", action="store_true", help="Launch the local browser-based control room")
    parser.add_argument("--desktop-runtime", action="store_true", help="Launch a real desktop session window and keep the Qt event loop alive")
    parser.add_argument("--profile-dir", type=Path, default=None, help="Completed profile directory for arming a desktop interview session")
    parser.add_argument("--company", type=str, default=None, help="Target company for the interview session")
    parser.add_argument("--role", type=str, default=None, help="Target role for the interview session")
    parser.add_argument("--use-global-hotkeys", action="store_true", help="Attempt to register the configured hotkey as a global system shortcut")
    parser.add_argument("--use-microphone", action="store_true", help="Use live microphone capture instead of the scripted audio recorder")
    parser.add_argument("--llm-base-url", type=str, default=None, help="Override the answer provider HTTP endpoint")
    parser.add_argument("--llm-timeout", type=float, default=None, help="Override the answer provider timeout in seconds")
    parser.add_argument("--start-session", action="store_true", help="Start the assembled desktop interview session lifecycle")
    parser.add_argument(
        "--session-command",
        type=str,
        choices=["start", "toggle", "status", "fallback", "export-diagnostics", "stop-worker"],
        default=None,
        help="Run a single session control command after assembling the desktop runner",
    )
    parser.add_argument(
        "--session-script",
        type=str,
        default=None,
        help="Run a comma-separated sequence like 'toggle,fallback:emergency,status' in one session",
    )
    parser.add_argument("--fallback-action", type=str, default=None, help="Fallback action to use with --session-command fallback")
    parser.add_argument("--diagnostics-path", type=Path, default=None, help="Destination for --session-command export-diagnostics")
    parser.add_argument("--session-state-path", type=Path, default=None, help="Persist or read a session state snapshot across CLI invocations")
    parser.add_argument("--session-database-path", type=Path, default=None, help="Persist and read session metadata/state from a SQLite database")
    parser.add_argument("--session-id", type=str, default=None, help="Reference a saved session by ID from the registry")
    parser.add_argument("--session-registry-path", type=Path, default=None, help="Custom path for the session registry file")
    parser.add_argument("--run-session-worker", action="store_true", help="Run a dedicated long-lived worker for a saved session ID")
    parser.add_argument("--worker-status", action="store_true", help="Display persisted worker status for a saved session ID")
    parser.add_argument("--worker-max-polls", type=int, default=None, help="Optional cap for worker loop polls; mainly useful for tests")
    parser.add_argument("--worker-poll-interval", type=float, default=0.25, help="Delay in seconds between worker queue polls")
    parser.add_argument("--list-sessions", action="store_true", help="List all saved sessions in the registry")
    parser.add_argument("--session-metrics", action="store_true", help="Display session statistics and metrics")
    parser.add_argument("--export-session", type=str, default=None, help="Export a session by ID to HTML format")
    parser.add_argument("--export-mobile-bridge", type=str, default=None, help="Export a session by ID to the mobile bridge JSON contract")
    parser.add_argument("--serve-mobile-bridge", action="store_true", help="Run the live mobile bridge HTTP server for mobile and web shells")
    parser.add_argument("--mobile-bridge-host", type=str, default="0.0.0.0", help="Host interface for the live mobile bridge server")
    parser.add_argument("--mobile-bridge-port", type=int, default=8765, help="Port for the live mobile bridge server")
    parser.add_argument("--export-path", type=Path, default=None, help="Destination path for --export-session (optional)")
    parser.add_argument("--compare-sessions", nargs=2, metavar=("PRIMARY_SESSION_ID", "SECONDARY_SESSION_ID"), default=None, help="Compare two saved sessions by ID")
    parser.add_argument("--process-session-commands", action="store_true", help="Process queued commands for a saved session by ID")
    parser.add_argument("--add-tag", type=str, default=None, help="Add a tag to a session (use with --session-id)")
    parser.add_argument("--remove-tag", type=str, default=None, help="Remove a tag from a session (use with --session-id)")
    parser.add_argument("--set-notes", type=str, default=None, help="Set notes for a session (use with --session-id)")
    parser.add_argument("--get-metadata", action="store_true", help="Get tags and notes for a session (use with --session-id)")
    parser.add_argument("--cleanup-sessions", action="store_true", help="Remove sessions older than a threshold")
    parser.add_argument("--hours-old", type=int, default=24, help="Threshold in hours for --cleanup-sessions (default: 24)")
    args = parser.parse_args(argv)

    if should_launch_packaged_preview(argv):
        if not acquire_packaged_preview_mutex():
            existing_url = wait_for_existing_dashboard_url()
            if existing_url is not None and is_mobile_bridge_healthy(host="127.0.0.1", port=8765):
                open_dashboard_in_browser(existing_url)
                return 0
        return launch_web_dashboard(registry_path=args.session_registry_path)

    if args.web_dashboard:
        return launch_web_dashboard(registry_path=args.session_registry_path)

    runtime = build_desktop_runtime(args.config_dir)
    runtime = apply_runtime_overrides(
        runtime,
        llm_base_url=args.llm_base_url,
        llm_timeout_seconds=args.llm_timeout,
    )
    runtime_config = runtime.runtime_config

    if args.gui_preview:
        from .overlay import launch_overlay_preview, qt_runtime_available, qt_runtime_error_message

        if not qt_runtime_available():
            print(qt_runtime_error_message())
            return 2
        return launch_overlay_preview(
            theme=runtime_config.app.theme,
            hotkey=runtime_config.app.hotkey,
            stt_model=runtime_config.model.stt_model,
            llm_model=runtime_config.model.llm_model,
        )

    if args.list_sessions:
        from .runtime_controller import list_sessions

        print(list_sessions(args.session_registry_path))
        return 0

    if args.session_metrics:
        from .runtime_controller import get_session_metrics

        print(get_session_metrics(args.session_registry_path))
        return 0

    if args.session_id and args.worker_status:
        from .runtime_controller import get_session_worker_status

        try:
            print(get_session_worker_status(args.session_id, args.session_registry_path))
        except KeyError as error:
            print(str(error))
            return 2
        return 0

    if args.session_id and args.run_session_worker:
        from .runtime_controller import run_session_worker

        try:
            print(
                run_session_worker(
                    args.session_id,
                    registry_path=args.session_registry_path,
                    config_dir=args.config_dir,
                    use_global_hotkeys=args.use_global_hotkeys,
                    llm_base_url=args.llm_base_url,
                    llm_timeout_seconds=args.llm_timeout,
                    session_database_path=args.session_database_path,
                    poll_interval_seconds=args.worker_poll_interval,
                    max_polls=args.worker_max_polls,
                )
            )
        except KeyError as error:
            print(str(error))
            return 2
        return 0

    if args.export_session:
        from .runtime_controller import export_session_html

        try:
            result = export_session_html(args.export_session, args.export_path, args.session_registry_path)
            print(result)
        except ValueError as error:
            print(str(error))
            return 2
        return 0

    if args.export_mobile_bridge:
        from mobile_app.runtime_bridge import export_mobile_bridge_snapshot

        try:
            export_path = args.export_path or Path("mobile_bridge.json")
            saved_path = export_mobile_bridge_snapshot(args.export_mobile_bridge, export_path, args.session_registry_path)
            print(f"Exported mobile bridge snapshot: {saved_path}")
        except KeyError as error:
            print(str(error))
            return 2
        return 0

    if args.serve_mobile_bridge:
        from mobile_app.live_bridge import serve_mobile_bridge

        print(f"Serving mobile bridge on http://{args.mobile_bridge_host}:{args.mobile_bridge_port}")
        serve_mobile_bridge(
            host=args.mobile_bridge_host,
            port=args.mobile_bridge_port,
            registry_path=args.session_registry_path,
        )
        return 0

    if args.compare_sessions:
        from .runtime_controller import compare_sessions

        try:
            result = compare_sessions(
                args.compare_sessions[0],
                args.compare_sessions[1],
                args.session_registry_path,
            )
            print(result)
        except ValueError as error:
            print(str(error))
            return 2
        return 0

    if args.add_tag or args.remove_tag or args.set_notes or args.get_metadata:
        if not args.session_id:
            print("Session ID is required for tag/note operations. Use --session-id SESSION_ID")
            return 2

        try:
            if args.add_tag:
                from .runtime_controller import add_session_tag
                result = add_session_tag(args.session_id, args.add_tag, args.session_registry_path)
                print(result)
            elif args.remove_tag:
                from .runtime_controller import remove_session_tag
                result = remove_session_tag(args.session_id, args.remove_tag, args.session_registry_path)
                print(result)
            elif args.set_notes:
                from .runtime_controller import set_session_notes
                result = set_session_notes(args.session_id, args.set_notes, args.session_registry_path)
                print(result)
            elif args.get_metadata:
                from .runtime_controller import get_session_metadata
                result = get_session_metadata(args.session_id, args.session_registry_path)
                print(result)
        except (KeyError, ValueError) as error:
            print(str(error))
            return 2
        return 0

    if args.session_id and args.process_session_commands:
        from .runtime_controller import build_registered_session_runner, process_session_command_queue

        try:
            runner = build_registered_session_runner(
                args.session_id,
                registry_path=args.session_registry_path,
                config_dir=args.config_dir,
                use_global_hotkeys=args.use_global_hotkeys,
                llm_base_url=args.llm_base_url,
                llm_timeout_seconds=args.llm_timeout,
                session_database_path=args.session_database_path,
            )
        except KeyError as error:
            print(str(error))
            return 2

        try:
            results = process_session_command_queue(runner)
            if results:
                print("Processed queued commands:\n\n" + "\n\n".join(results))
            else:
                print("No queued commands found for the session.")
        except ValueError as error:
            print(str(error))
            return 2
        finally:
            runner.stop()
        return 0

    if args.cleanup_sessions:
        from .runtime_controller import cleanup_sessions

        result = cleanup_sessions(hours_old=args.hours_old, registry_path=args.session_registry_path)
        print(result)
        return 0

    if args.session_id and args.session_command:
        from .runtime_controller import enqueue_session_command, find_session_registry_entry, format_session_state_summary, load_registered_session_state

        if args.session_command != "status":
            if args.session_command == "start":
                print("Session ID mode does not support the start command.")
                return 2

            try:
                queue_path = enqueue_session_command(
                    args.session_id,
                    args.session_command,
                    args.session_registry_path,
                    fallback_action=args.fallback_action,
                    diagnostics_destination=args.diagnostics_path,
                )
            except KeyError as error:
                print(str(error))
                return 2

            print(f"Queued session command '{args.session_command}' for {args.session_id}: {queue_path}")
            return 0

        try:
            entry = find_session_registry_entry(args.session_id, args.session_registry_path)
            payload = load_registered_session_state(args.session_id, args.session_registry_path)
        except KeyError as error:
            print(str(error))
            return 2

        print(build_runtime_summary(runtime))
        print()
        print(format_session_state_summary(payload))
        print(f"Session registry path: {args.session_registry_path or Path(str(entry['session_state_path'])).parent / 'session_registry.json'}")
        return 0

    if args.profile_dir and args.company and args.role:
        from .runtime_controller import (
            build_desktop_session,
            build_desktop_session_runtime,
            build_session_runner,
            build_session_summary,
            execute_runner_command,
            execute_runner_script,
        )

        if args.desktop_runtime:
            from .overlay import qt_runtime_available, qt_runtime_error_message
            if not qt_runtime_available():
                print(qt_runtime_error_message())
                return 2

            controller, overlay_runtime = build_desktop_session_runtime(
                profile_directory=args.profile_dir,
                company_name=args.company,
                role_title=args.role,
                config_dir=args.config_dir,
                use_global_hotkeys=args.use_global_hotkeys,
                prefer_microphone=args.use_microphone,
                llm_base_url=args.llm_base_url,
                llm_timeout_seconds=args.llm_timeout,
            )
            try:
                strategy_path = controller.arm_session()
                controller.overlay_controller.update(controller.interview_mode.overlay_state)
                print(build_runtime_summary(runtime))
                print()
                print(build_session_summary(controller, strategy_path))
                return overlay_runtime.run()
            finally:
                controller.shutdown()

        if args.start_session or args.session_command or args.session_script:
            runner = build_session_runner(
                profile_directory=args.profile_dir,
                company_name=args.company,
                role_title=args.role,
                config_dir=args.config_dir,
                use_global_hotkeys=args.use_global_hotkeys,
                prefer_microphone=args.use_microphone,
                llm_base_url=args.llm_base_url,
                llm_timeout_seconds=args.llm_timeout,
                session_state_path=args.session_state_path,
                session_registry_path=args.session_registry_path,
                session_database_path=args.session_database_path,
            )
            try:
                try:
                    if args.session_script:
                        results = execute_runner_script(
                            runner,
                            [item for item in args.session_script.split(",")],
                        )
                        result = "\n\n".join(results)
                    else:
                        result = execute_runner_command(
                            runner,
                            args.session_command or "start",
                            fallback_action=args.fallback_action,
                            diagnostics_destination=args.diagnostics_path,
                        )
                except ValueError as error:
                    print(str(error))
                    return 2
                print(build_runtime_summary(runtime))
                print()
                print(result)
            finally:
                runner.stop()
            return 0

        controller = build_desktop_session(
            profile_directory=args.profile_dir,
            company_name=args.company,
            role_title=args.role,
            config_dir=args.config_dir,
            use_global_hotkeys=args.use_global_hotkeys,
            prefer_microphone=args.use_microphone,
            llm_base_url=args.llm_base_url,
            llm_timeout_seconds=args.llm_timeout,
        )
        try:
            strategy_path = controller.arm_session()
            print(build_runtime_summary(runtime))
            print()
            print(build_session_summary(controller, strategy_path))
        finally:
            controller.shutdown()
        return 0

    print(build_runtime_summary(runtime))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as error:
        log_path = write_startup_error_log(error)
        show_packaged_error_dialog(
            "Career Copilot could not start. Check the startup log at:\n"
            f"{log_path}"
        )
        raise