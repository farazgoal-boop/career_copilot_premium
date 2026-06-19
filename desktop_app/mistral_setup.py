"""First-run Mistral API key setup and validation."""

from __future__ import annotations

import json
import os
import threading
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from urllib import error, request

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication as QtApplication

from runtime_paths import env_file_paths, load_env_file, primary_env_file_path

MISTRAL_MODELS_URL = "https://api.mistral.ai/v1/models"
MISTRAL_CONSOLE_URL = "https://console.mistral.ai/"

SETUP_STYLE = """
    QDialog {
        background: #0D1117;
        color: #E6EDF3;
    }
    QLabel {
        color: #E6EDF3;
        font-family: 'Segoe UI';
    }
    QLineEdit {
        background: #161B22;
        color: #E6EDF3;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 10px 12px;
        font-size: 12px;
    }
    QPushButton {
        background: #21262D;
        color: #E6EDF3;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 8px 14px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #30363D;
    }
"""


def mistral_api_key() -> str:
    load_env_file()
    return os.environ.get("MISTRAL_API_KEY", "").strip()


def has_mistral_api_key() -> bool:
    return bool(mistral_api_key())


def save_mistral_api_key(api_key: str) -> Path:
    key = api_key.strip()
    if not key:
        raise ValueError("API key cannot be empty.")
    target = primary_env_file_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PermissionError(
            f"Could not create settings folder at {target.parent}. ({exc})"
        ) from exc
    lines: list[str] = []
    if target.is_file():
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.strip().startswith("MISTRAL_API_KEY="):
            new_lines.append(f"MISTRAL_API_KEY={key}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(f"MISTRAL_API_KEY={key}")
    try:
        target.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot write API key to {target}. Run as user (not Program Files). "
            "The app will save to your user AppData folder automatically."
        ) from exc
    os.environ["MISTRAL_API_KEY"] = key
    return target


def validate_mistral_api_key(api_key: str | None = None) -> tuple[bool, str]:
    key = (api_key or mistral_api_key()).strip()
    if not key:
        return False, "API key is missing."
    if len(key) < 8:
        return False, "API key format looks too short."
    try:
        http_request = request.Request(
            MISTRAL_MODELS_URL,
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        )
        with request.urlopen(http_request, timeout=12.0) as response:
            if response.status != 200:
                return False, f"Mistral API returned status {response.status}."
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            return False, "Unexpected Mistral API response."
        return True, "Mistral Connected"
    except error.HTTPError as http_error:
        if http_error.code in {401, 403}:
            return False, "Invalid Mistral API key."
        return False, f"Mistral API error ({http_error.code})."
    except (OSError, TimeoutError, ValueError, error.URLError) as exc:
        return False, f"Could not reach Mistral API: {exc}"


_API_VALIDATION_CACHE: dict[str, object] = {"at": 0.0, "ok": False, "message": ""}


def mistral_connection_status() -> tuple[bool, str]:
    """Fast UI status — never blocks on network."""
    if not has_mistral_api_key():
        return False, "API key is missing."
    age = time.time() - float(_API_VALIDATION_CACHE.get("at", 0.0))
    if age < 300 and _API_VALIDATION_CACHE.get("message"):
        return bool(_API_VALIDATION_CACHE.get("ok", True)), str(_API_VALIDATION_CACHE.get("message", "Mistral Connected"))
    return True, "Mistral key saved"


def refresh_mistral_validation_async(force: bool = False) -> None:
    """Validate Mistral API key in a background thread (overlay-safe)."""
    if not has_mistral_api_key():
        return
    age = time.time() - float(_API_VALIDATION_CACHE.get("at", 0.0))
    if not force and age < 300:
        return
    if _API_VALIDATION_CACHE.get("running"):
        return
    _API_VALIDATION_CACHE["running"] = True

    def _worker() -> None:
        try:
            ok, message = validate_mistral_api_key()
            _API_VALIDATION_CACHE["at"] = time.time()
            _API_VALIDATION_CACHE["ok"] = ok
            _API_VALIDATION_CACHE["message"] = message if ok else message
        finally:
            _API_VALIDATION_CACHE["running"] = False

    threading.Thread(target=_worker, name="mistral-api-validate", daemon=True).start()


def run_first_time_setup_wizard(qt_app: "QtApplication | None" = None) -> bool:
    """Show PySide6 setup dialog. Returns True when key saved and valid."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QVBoxLayout,
        )
    except ImportError:
        print("[setup] PySide6 unavailable — add MISTRAL_API_KEY to .env manually.")
        return has_mistral_api_key()

    app = qt_app or QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication must be created before the Mistral setup wizard.")

    dialog = QDialog()
    dialog.setWindowTitle("Career Copilot Premium — First-Time Setup")
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
    dialog.setMinimumWidth(520)
    dialog.setStyleSheet(SETUP_STYLE)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(24, 24, 24, 24)

    logo = QLabel("Career Copilot Premium")
    logo.setStyleSheet("font-size:20px;font-weight:700;color:#58A6FF;")
    layout.addWidget(logo)

    title = QLabel("Connect your free Mistral API key")
    title.setStyleSheet("font-size:14px;font-weight:600;")
    title.setWordWrap(True)
    layout.addWidget(title)

    hint = QLabel(
        "Get a free key at console.mistral.ai — required once per computer.\n"
        "Sign up → API Keys → Create key → paste below."
    )
    hint.setWordWrap(True)
    hint.setStyleSheet("color:#8B949E;font-size:12px;")
    layout.addWidget(hint)

    key_input = QLineEdit()
    key_input.setPlaceholderText("Paste Mistral API key here...")
    key_input.setEchoMode(QLineEdit.Password)
    layout.addWidget(key_input)

    status = QLabel("")
    status.setWordWrap(True)
    status.setStyleSheet("font-size:12px;")
    layout.addWidget(status)

    row = QHBoxLayout()
    free_btn = QPushButton("Get Free Key at console.mistral.ai")
    verify_btn = QPushButton("Verify & Save")
    verify_btn.setStyleSheet(
        "QPushButton{background:#238636;color:#fff;border:1px solid #2EA043;}"
        "QPushButton:hover{background:#2EA043;}"
    )
    row.addWidget(free_btn)
    row.addStretch()
    row.addWidget(verify_btn)
    layout.addLayout(row)

    save_hint = QLabel(f"Key saves to: {primary_env_file_path()}")
    save_hint.setWordWrap(True)
    save_hint.setStyleSheet("color:#8B949E;font-size:10px;")
    layout.addWidget(save_hint)

    try:
        from .premium_footer import BRAND_TAGLINE, PREMIUM_FOOTER_LINKS

        footer_lbl = QLabel(BRAND_TAGLINE)
        footer_lbl.setStyleSheet("color:#8B949E;font-size:10px;font-weight:600;")
        layout.addWidget(footer_lbl)
        footer_row = QHBoxLayout()
        footer_row.setSpacing(6)
        for link in PREMIUM_FOOTER_LINKS:
            btn = QPushButton(link.icon)
            btn.setToolTip(f"{link.label}: {link.url}")
            btn.setFixedSize(30, 26)
            btn.setStyleSheet(
                f"QPushButton{{background:#21262D;color:{link.color};"
                f"border:1px solid #30363D;border-radius:6px;font-size:11px;font-weight:700;}}"
                "QPushButton:hover{background:#30363D;}"
            )
            btn.clicked.connect(lambda _checked=False, url=link.url: webbrowser.open(url))
            footer_row.addWidget(btn)
        footer_row.addStretch()
        layout.addLayout(footer_row)
    except Exception:
        pass

    def open_console() -> None:
        try:
            webbrowser.open(MISTRAL_CONSOLE_URL)
        except OSError:
            status.setText("Open https://console.mistral.ai/ in your browser.")

    def save_key() -> None:
        value = key_input.text().strip()
        if not value:
            status.setText("❌ API key cannot be empty.")
            status.setStyleSheet("color:#F85149;font-size:12px;")
            return
        status.setText("Testing key with Mistral API...")
        status.setStyleSheet("color:#D29922;font-size:12px;")
        verify_btn.setEnabled(False)
        app.processEvents()
        try:
            ok, message = validate_mistral_api_key(value)
            if not ok:
                status.setText(f"❌ {message}")
                status.setStyleSheet("color:#F85149;font-size:12px;")
                return
            saved_path = save_mistral_api_key(value)
            status.setText(f"✅ Key saved to {saved_path}. Starting Career Copilot Premium...")
            status.setStyleSheet("color:#3FB950;font-size:12px;")
            app.processEvents()
            dialog.accept()
        except PermissionError:
            status.setText(
                f"❌ Cannot save to Program Files. Key will save to:\n{primary_env_file_path()}"
            )
        except Exception as exc:  # noqa: BLE001
            status.setText(f"❌ {exc}")
            status.setStyleSheet("color:#F85149;font-size:12px;")
        finally:
            verify_btn.setEnabled(True)

    free_btn.clicked.connect(open_console)
    verify_btn.clicked.connect(save_key)
    key_input.returnPressed.connect(save_key)

    return dialog.exec() == QDialog.DialogCode.Accepted


def ensure_mistral_api_key_configured(
    on_status: Callable[[str], None] | None = None,
    qt_app: "QtApplication | None" = None,
) -> bool:
    """Return True when a valid Mistral key is available."""
    if has_mistral_api_key():
        ok, message = validate_mistral_api_key()
        if ok:
            return True
        if on_status:
            on_status(message)
    if on_status:
        on_status("API key required — opening setup...")
    return run_first_time_setup_wizard(qt_app=qt_app)
