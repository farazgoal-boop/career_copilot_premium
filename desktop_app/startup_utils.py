"""Startup helpers: logging, splash, port selection, runtime checks."""



from __future__ import annotations



import os

import socket

import sys

import traceback

from datetime import datetime, timezone

from pathlib import Path



from runtime_paths import DASHBOARD_PORT, env_file_paths, logs_root, repo_root





STARTUP_LOG_NAME = "startup_error.log"

VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"





def startup_log_path() -> Path:

    path = logs_root()

    path.mkdir(parents=True, exist_ok=True)

    return path / STARTUP_LOG_NAME





def log_startup(message: str) -> None:

    timestamp = datetime.now(timezone.utc).isoformat()

    line = f"[{timestamp}] {message}\n"

    try:

        with startup_log_path().open("a", encoding="utf-8") as handle:

            handle.write(line)

    except OSError:

        pass





def log_startup_exception(context: str, exc: BaseException) -> None:

    log_startup(f"{context}: {exc}")

    log_startup(traceback.format_exc())





def is_port_available(host: str, port: int) -> bool:

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:

        probe.settimeout(0.4)

        return probe.connect_ex((host, port)) != 0





def resolve_dashboard_port(preferred: int = DASHBOARD_PORT) -> int:

    for candidate in (preferred, preferred + 1, preferred + 2):

        if is_port_available("127.0.0.1", candidate):

            os.environ["DASHBOARD_PORT"] = str(candidate)

            if candidate != preferred:

                log_startup(f"Port {preferred} busy - using {candidate} instead.")

            return candidate

    log_startup(f"Ports {preferred}-{preferred + 2} busy - forcing {preferred}.")

    return preferred





def _qt_runtime_loaded() -> bool:
    """True when PySide6 already imported — runtime DLLs are usable."""
    try:
        import PySide6.QtCore  # noqa: F401

        return True
    except Exception:
        return False


def _vc_dll_present() -> bool:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    search_dirs = [
        Path(system_root) / "System32",
        Path(system_root) / "SysWOW64",
        repo_root(),
        repo_root() / "_internal",
    ]
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        search_dirs.append(Path(meipass))
    for folder in search_dirs:
        if (folder / "vcruntime140.dll").is_file() and (folder / "msvcp140.dll").is_file():
            return True
    return False


def check_vc_redistributable() -> tuple[bool, str]:
    if sys.platform != "win32":
        return True, ""
    # Packaged app already loaded Qt before this check — do not block on a false alarm.
    if getattr(sys, "frozen", False) and _qt_runtime_loaded():
        return True, ""
    if _vc_dll_present():
        return True, ""
    if _qt_runtime_loaded():
        return True, ""
    return False, (
        "One Windows component is missing (Visual C++ Runtime). "
        "Click \"Install Fix\" on the next screen, then open Career Copilot again."
    )





def _bundle_folder_exists(folder_name: str, root: Path) -> bool:

    """Return True when a bundled folder exists in dev or PyInstaller layouts."""

    candidates = [

        root / folder_name,

        root / "_internal" / folder_name,

    ]

    meipass = getattr(sys, "_MEIPASS", "")

    if meipass:

        candidates.append(Path(meipass) / folder_name)

    return any(path.is_dir() for path in candidates)





def verify_startup_environment() -> tuple[bool, str]:

    """Validate folders, .env presence, and runtime prerequisites before launch."""

    root = repo_root()

    issues: list[str] = []

    frozen = getattr(sys, "frozen", False)



    for folder_name in ("web_app", "desktop_app"):

        if not _bundle_folder_exists(folder_name, root):

            issues.append(f"Missing required folder: {folder_name}/")



    if not frozen:

        data_path = root / "data"

        if not data_path.is_dir():

            issues.append("Missing required folder: data/")



    env_candidates = env_file_paths()

    env_exists = any(path.is_file() for path in env_candidates)

    example_path = root / ".env.example"

    if not env_exists:

        has_example = example_path.is_file() or (root / "_internal" / ".env.example").is_file()
        if has_example:
            log_startup("No .env yet - first-run setup will create it from your Mistral API key.")
        else:
            issues.append("No .env or .env.example found next to the application.")



    vc_ok, vc_message = check_vc_redistributable()

    if not vc_ok:

        issues.append(vc_message)



    port = resolve_dashboard_port()

    log_startup(f"Dashboard port resolved to {port}")

    log_startup(f"Application root: {root}")

    log_startup(f"Frozen bundle: {frozen}")

    log_startup(f".env present: {env_exists}")



    if issues:

        message = "\n".join(issues)

        log_startup(f"Startup environment check failed:\n{message}")

        return False, message

    return True, ""





def offer_vc_redistributable_install() -> bool:
    """Download and silently install VC++ runtime when possible."""
    if sys.platform != "win32":
        return False
    import subprocess
    import tempfile
    import urllib.request

    try:
        target = Path(tempfile.gettempdir()) / "CareerCopilot_vc_redist.x64.exe"
        urllib.request.urlretrieve(VC_REDIST_URL, target)
        subprocess.run(
            [str(target), "/install", "/quiet", "/norestart"],
            check=False,
            timeout=180,
        )
        return target.exists()
    except Exception as exc:
        log_startup_exception("VC++ auto-install failed", exc)
        return False


def show_startup_error_dialog(message: str, qt_app: object | None = None) -> None:
    log_startup(message)
    try:
        import webbrowser

        from PySide6.QtWidgets import QApplication, QMessageBox

        app = qt_app or QApplication.instance()
        if app is None:
            print(f"[startup-error] {message}")
            return

        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Career Copilot Premium")
        is_vc_issue = "Visual C++" in message or "Runtime" in message
        box.setText("Almost ready — one quick fix needed" if is_vc_issue else "Startup Error")
        box.setInformativeText(message)
        box.setDetailedText(f"Log file: {startup_log_path()}")
        install_btn = None
        if is_vc_issue:
            install_btn = box.addButton("Install Fix", QMessageBox.ActionRole)
            box.addButton("Open Download Page", QMessageBox.ActionRole)
        box.addButton("OK", QMessageBox.AcceptRole)
        box.exec()
        clicked = box.clickedButton()
        if install_btn is not None and clicked == install_btn:
            if offer_vc_redistributable_install():
                QMessageBox.information(
                    box,
                    "Career Copilot Premium",
                    "Windows component installed. Please open Career Copilot Premium again.",
                )
            else:
                QMessageBox.warning(
                    box,
                    "Career Copilot Premium",
                    "Automatic install could not finish. Use \"Open Download Page\" "
                    "and run the installer, then open the app again.",
                )
        elif clicked and clicked.text() == "Open Download Page":
            try:
                webbrowser.open(VC_REDIST_URL)
            except OSError:
                pass
    except Exception:
        print(f"[startup-error] {message}")





def show_splash_while_loading(

    label: str = "Starting Career Copilot Premium...",

    qt_app: object | None = None,

) -> object | None:

    try:

        from PySide6.QtCore import Qt

        from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget



        app = qt_app or QApplication.instance()

        if app is None:

            return None

        splash = QWidget()

        splash.setWindowTitle("Career Copilot Premium")

        splash.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

        splash.setFixedSize(360, 120)

        splash.setStyleSheet("background:#0D1117;color:#E6EDF3;border:1px solid #30363D;border-radius:12px;")

        layout = QVBoxLayout(splash)

        text = QLabel(label)

        text.setAlignment(Qt.AlignCenter)

        text.setWordWrap(True)

        layout.addWidget(text)

        splash.show()

        app.processEvents()

        return splash

    except Exception as exc:  # noqa: BLE001

        log_startup_exception("Splash screen unavailable", exc)

        return None





def close_splash(splash: object | None) -> None:

    if splash is None:

        return

    try:

        splash.close()  # type: ignore[attr-defined]

    except Exception:

        pass





def frozen_app_root() -> Path:

    return repo_root()


