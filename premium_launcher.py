"""Premium portable launcher — dashboard, mobile bridge, and overlay from one folder (USB-safe)."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from typing import TYPE_CHECKING

os.environ.setdefault("CCP_REQUIRE_LICENSE", "1")

if sys.platform == "darwin":
    # PyInstaller-frozen Python on macOS has no access to the system cert
    # store, which makes urllib's default HTTPS context fail with
    # CERTIFICATE_VERIFY_FAILED. Point it at certifi's bundled CA file.
    import ssl

    import certifi

    _MAC_CAFILE = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", _MAC_CAFILE)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _MAC_CAFILE)
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=_MAC_CAFILE)

from runtime_paths import (  # noqa: E402
    MOBILE_BRIDGE_PORT,
    PORTABLE_FLAG_FILENAME,
    configure_runtime_environment,
    default_bridge_base_url,
    get_dashboard_port,
    install_root_is_readonly,
    instance_lock_path,
    is_portable_mode,
    load_env_file,
    overlay_show_flag_path,
    portable_status_payload,
    repo_root,
)

# Portable mode only when portable.flag exists (USB/dev). Never force on Program Files install.
if not install_root_is_readonly() and (repo_root() / PORTABLE_FLAG_FILENAME).is_file():
    os.environ.setdefault("CAREER_COPILOT_PORTABLE", "1")

if TYPE_CHECKING:
    from mobile_app.live_bridge import MobileBridgeServer
    from PySide6.QtWidgets import QApplication as QtApplication


def _ensure_qt_application() -> "QtApplication":
    """Create the process-wide QApplication singleton once."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _wait_for_dashboard(host: str, port: int, timeout_seconds: float = 15.0) -> bool:
    deadline = time.time() + timeout_seconds
    url = f"http://{host}:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except (OSError, TimeoutError, urllib.error.URLError):
            time.sleep(0.25)
    return False


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_instance_lock() -> dict | None:
    try:
        payload = json.loads(instance_lock_path().read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_instance_lock(port: int) -> None:
    try:
        path = instance_lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"pid": os.getpid(), "port": port}),
            encoding="utf-8",
        )
    except OSError:
        pass


def _clear_instance_lock() -> None:
    try:
        instance_lock_path().unlink(missing_ok=True)
    except OSError:
        pass


def _reactivate_running_instance(existing: dict) -> None:
    """Bring an already-running instance's dashboard/overlay to the front instead
    of silently doing nothing (the previous behavior when the icon was double-clicked
    while a prior, still-alive instance was hidden in the background)."""
    port = existing.get("port") or get_dashboard_port()
    print(f"[premium] Career Copilot Premium is already running (pid {existing.get('pid')}). Reopening...")
    webbrowser.open(f"http://127.0.0.1:{port}")
    try:
        flag = overlay_show_flag_path()
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()
    except OSError:
        pass


class PremiumRuntime:
    def __init__(self) -> None:
        self.flask_server = None
        self.flask_thread: threading.Thread | None = None
        self.mobile_bridge: MobileBridgeServer | None = None
        self.dashboard_port = get_dashboard_port()

    @property
    def dashboard_url(self) -> str:
        return f"http://127.0.0.1:{self.dashboard_port}"

    def start_services(self) -> None:
        from werkzeug.serving import make_server

        from mobile_app.live_bridge import start_mobile_bridge_server
        from web_app.app import create_app

        registry = configure_runtime_environment()

        try:
            self.mobile_bridge = start_mobile_bridge_server(
                host="0.0.0.0",
                port=MOBILE_BRIDGE_PORT,
                registry_path=registry,
            )
            os.environ["BRIDGE_BASE_URL"] = self.mobile_bridge.url
        except OSError as error:
            from desktop_app.startup_utils import log_startup

            log_startup(f"Mobile bridge unavailable: {error}")
            self.mobile_bridge = None

        app = create_app()
        app.config["SESSION_REGISTRY_PATH"] = str(registry)
        bridge_url = os.environ.get("BRIDGE_BASE_URL", "").strip() or default_bridge_base_url()
        app.config["BRIDGE_BASE_URL"] = bridge_url

        try:
            self.flask_server = make_server("127.0.0.1", self.dashboard_port, app, threaded=True)
        except OSError as error:
            raise RuntimeError(
                f"Could not start dashboard on port {self.dashboard_port}. "
                f"Close other apps using this port or restart the computer. ({error})"
            ) from error

        self.flask_thread = threading.Thread(
            target=self.flask_server.serve_forever,
            name="career-copilot-flask",
            daemon=True,
        )
        self.flask_thread.start()
        if not _wait_for_dashboard("127.0.0.1", self.dashboard_port):
            raise RuntimeError(
                f"Dashboard did not become healthy on port {self.dashboard_port}. "
                f"See logs/startup_error.log"
            )

    def stop_services(self) -> None:
        if self.flask_server is not None:
            self.flask_server.shutdown()
            self.flask_server = None
        if self.flask_thread is not None:
            self.flask_thread.join(timeout=5)
            self.flask_thread = None
        if self.mobile_bridge is not None:
            self.mobile_bridge.stop()
            self.mobile_bridge = None


def _run_overlay_event_loop(services: PremiumRuntime, qt_app: "QtApplication") -> int:
    from PySide6.QtCore import QObject, QTimer, Qt, Signal
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

    class SessionPollSignals(QObject):
        payload_ready = Signal(str, object)

    qt_app = QApplication.instance() or qt_app or QApplication(sys.argv)

    from desktop_app.overlay import (
        build_answer_overlay,
        build_listening_overlay,
        create_overlay_runtime,
        qt_runtime_available,
        qt_runtime_error_message,
    )

    if not qt_runtime_available():
        from desktop_app.startup_utils import show_startup_error_dialog

        webbrowser.open(services.dashboard_url)
        print(f"[premium] Dashboard ready: {services.dashboard_url}")
        print("[premium] Overlay unavailable — install PySide6 in the project venv.")
        show_startup_error_dialog(
            f"{qt_runtime_error_message()}\n\n"
            "The floating overlay window and F2/F3 hotkeys will not be available "
            "this session — only the browser dashboard will work.\n\n"
            "Fix: open Terminal in the app folder and run:\n"
            "python3 -m pip install --force-reinstall PySide6",
            qt_app=qt_app,
        )
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0

    runtime = create_overlay_runtime(qt_app=qt_app)
    window = runtime.controller.window
    if window is None:
        raise RuntimeError("Overlay window could not be created.")

    window.show()
    window.raise_()
    window.activateWindow()
    window.dashboard_url = services.dashboard_url

    last_status = ""
    last_answer = ""

    def toggle_overlay_visibility() -> None:
        if window.isVisible():
            window.hide()
        else:
            window.show()
            window.raise_()
            window.activateWindow()

    # Use a QObject signal so keyboard callbacks (background thread) safely
    # dispatch onto the Qt main thread before touching any Qt widget.
    class _HotkeySignals(QObject):
        listen_triggered = Signal()
        toggle_triggered = Signal()

    _hotkey_signals = _HotkeySignals()
    _hotkey_signals.listen_triggered.connect(window._on_live_listen)
    _hotkey_signals.toggle_triggered.connect(toggle_overlay_visibility)

    _using_global_hotkeys = False
    try:
        import keyboard as _kb  # type: ignore[import-not-found]
        _kb.add_hotkey("f2", _hotkey_signals.listen_triggered.emit)
        _kb.add_hotkey("f3", _hotkey_signals.toggle_triggered.emit)
        _using_global_hotkeys = True
    except Exception:
        pass

    if not _using_global_hotkeys:
        # Fallback: Qt application shortcuts (work only when a Qt window has focus)
        listen_shortcut = QShortcut(QKeySequence("F2"), window)
        listen_shortcut.activated.connect(window._on_live_listen)
        listen_shortcut.setContext(Qt.ApplicationShortcut)
        visibility_shortcut = QShortcut(QKeySequence("F3"), window)
        visibility_shortcut.activated.connect(toggle_overlay_visibility)
        visibility_shortcut.setContext(Qt.ApplicationShortcut)

    # System tray icon: the overlay's own close button only hides the window
    # (see TransparentOverlayWindow.closeEvent) so the process would otherwise
    # keep running invisibly with no way to actually quit it.
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(qt_app)
        tray.setIcon(qt_app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        tray.setToolTip("Career Copilot Premium")

        tray_menu = QMenu()
        open_action = tray_menu.addAction("Open Dashboard")
        open_action.triggered.connect(lambda: webbrowser.open(services.dashboard_url))
        show_action = tray_menu.addAction("Show Overlay")
        show_action.triggered.connect(lambda: (window.show(), window.raise_(), window.activateWindow()))
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit Career Copilot Premium")

        def _quit_app() -> None:
            tray.hide()
            qt_app.quit()

        quit_action.triggered.connect(_quit_app)
        tray.setContextMenu(tray_menu)

        def _on_tray_activated(reason: "QSystemTrayIcon.ActivationReason") -> None:
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                window.show()
                window.raise_()
                window.activateWindow()

        tray.activated.connect(_on_tray_activated)
        tray.show()

    from runtime_paths import overlay_show_flag_path as _overlay_flag_path_fn
    _overlay_flag = _overlay_flag_path_fn()
    _overlay_flag.parent.mkdir(parents=True, exist_ok=True)

    poll_in_flight = {"active": False}
    poll_signals = SessionPollSignals()

    def _apply_session_payload(payload: dict[str, object]) -> None:
        nonlocal last_status, last_answer
        overlay = payload.get("overlay", {})
        snapshot = payload.get("snapshot", {})
        status = str(overlay.get("status", "idle"))
        answer = (
            overlay.get("body")
            or overlay.get("suggested_answer")
            or snapshot.get("last_answer")
            or ""
        )
        if status == last_status and answer == last_answer:
            return
        last_status = status
        last_answer = str(answer)

        if status == "answer_ready":
            transcript = (
                overlay.get("headline")
                or overlay.get("transcript")
                or snapshot.get("last_transcript")
                or "Question captured"
            )
            state = build_answer_overlay(
                transcript=str(transcript),
                suggested_answer=str(answer or "Answer generating..."),
                alternatives=list(overlay.get("alternatives", [])),
                confidence_score=int(overlay.get("confidence_score", 91) or 91),
                provider_status=str(overlay.get("provider_status", "AI") or "AI"),
            )
            runtime.controller.update(state)
            window.show()
        elif status == "listening":
            runtime.controller.update(build_listening_overlay())

    def poll_session_updates() -> None:
        # Check for overlay-show flag written by POST /api/overlay/show.
        # This runs on the Qt main thread (QTimer callback) so show() is safe here.
        if _overlay_flag.exists():
            try:
                _overlay_flag.unlink(missing_ok=True)
            except OSError:
                pass
            window.show()
            window.raise_()
            window.activateWindow()

        if poll_in_flight["active"]:
            return
        poll_in_flight["active"] = True

        def _worker() -> None:
            try:
                with urllib.request.urlopen(
                    f"{services.dashboard_url}/api/sessions/recent",
                    timeout=1.5,
                ) as response:
                    sessions = json.loads(response.read()).get("sessions", [])
                if not sessions:
                    return

                session_id = str(sessions[0].get("session_id", "")).strip()
                if not session_id:
                    return

                with urllib.request.urlopen(
                    f"{services.dashboard_url}/api/session/{session_id}",
                    timeout=2.0,
                ) as response:
                    payload = json.loads(response.read())

                poll_signals.payload_ready.emit(session_id, payload)
            except Exception:
                pass
            finally:
                poll_in_flight["active"] = False

        threading.Thread(target=_worker, name="overlay-session-poll", daemon=True).start()

    def _on_poll_payload(session_id: str, payload: object) -> None:
        window.current_session_id = session_id
        if isinstance(payload, dict):
            _apply_session_payload(payload)

    poll_signals.payload_ready.connect(_on_poll_payload)

    timer = QTimer()
    timer.timeout.connect(poll_session_updates)
    timer.start(4000)

    webbrowser.open(services.dashboard_url)
    status = portable_status_payload()
    print("[premium] Career Copilot Premium is running.")
    print(f"[premium] Dashboard: {services.dashboard_url}")
    print(f"[premium] Data folder: {status['data_root']}")
    if _using_global_hotkeys:
        print("[premium] F2 / F3: global system hotkeys (work even when overlay is hidden).")
    else:
        print("[premium] F2 / F3: Qt application shortcuts (require overlay focus).")
    print("[premium] Press F2 or click Listen in the overlay to capture interviewer speech.")
    print("[premium] Press F3 to show or hide the overlay. Manual Input still works for typed questions.")

    try:
        return qt_app.exec()
    finally:
        services.stop_services()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Career Copilot Premium desktop runtime")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Dashboard HTTP port (default: 5000, or next free port if busy)",
    )
    args = parser.parse_args()
    if args.port is not None:
        if args.port < 1 or args.port > 65535:
            print(f"[premium] Invalid port: {args.port}", file=sys.stderr)
            return 2
        os.environ["DASHBOARD_PORT"] = str(args.port)

    configure_runtime_environment()

    # If a previous launch is still alive in the background (e.g. the overlay
    # was hidden, not quit), reopen its dashboard/overlay instead of silently
    # doing nothing — this is what made the app icon look broken on relaunch.
    existing = _read_instance_lock()
    if existing and _is_pid_alive(int(existing.get("pid", -1) or -1)):
        _reactivate_running_instance(existing)
        return 0

    from desktop_app.mistral_setup import ensure_mistral_api_key_configured
    from desktop_app.startup_utils import (
        close_splash,
        log_startup,
        log_startup_exception,
        show_splash_while_loading,
        show_startup_error_dialog,
        verify_startup_environment,
    )

    qt_app = _ensure_qt_application()
    splash = show_splash_while_loading("Starting Career Copilot Premium...", qt_app=qt_app)
    try:
        log_startup("Career Copilot Premium startup begin")
        load_env_file()

        env_ok, env_message = verify_startup_environment()
        if not env_ok:
            close_splash(splash)
            splash = None
            show_startup_error_dialog(
                f"{env_message}\n\nDetails saved to logs/startup_error.log",
                qt_app=qt_app,
            )
            return 1

        _write_instance_lock(get_dashboard_port())

        close_splash(splash)
        splash = None
        qt_app.processEvents()

        mistral_ok, mistral_message = ensure_mistral_api_key_configured(
            on_status=log_startup, qt_app=qt_app
        )
        if not mistral_ok:
            log_startup(f"Continuing without a working Mistral key: {mistral_message}")

        if not is_portable_mode():
            print("[premium] Tip: add portable.flag to keep all data on this USB folder.")

        splash = show_splash_while_loading("Loading dashboard and overlay...", qt_app=qt_app)
        qt_app.processEvents()
        services = PremiumRuntime()
        services.start_services()
        close_splash(splash)
        splash = None
        print("Career Copilot Premium is running — close this window to stop the app")
        return _run_overlay_event_loop(services, qt_app)
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        log_startup_exception("Startup failed", error)
        close_splash(splash)
        show_startup_error_dialog(
            f"{error}\n\nDetails saved to logs/startup_error.log",
            qt_app=qt_app,
        )
        return 1
    finally:
        close_splash(splash)
        _clear_instance_lock()


if __name__ == "__main__":
    raise SystemExit(main())
