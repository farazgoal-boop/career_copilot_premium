"""Single-click launcher for Career Copilot desktop + mobile bridge services."""

from __future__ import annotations

import socket
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from threading import Thread

from werkzeug.serving import make_server

from mobile_app.live_bridge import MobileBridgeServer, start_mobile_bridge_server
from runtime_paths import (
    DASHBOARD_PORT,
    MOBILE_BRIDGE_PORT,
    configure_runtime_environment,
    default_bridge_base_url,
    session_registry_path,
)
from web_app.app import create_app

try:
    from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
except ImportError as error:  # pragma: no cover - runtime guard for incomplete installs.
    raise RuntimeError("PySide6 is required for the launcher system tray UI.") from error


def _wait_for_dashboard(host: str, port: int, timeout_seconds: float = 12.0) -> bool:
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


class FlaskRuntime:
    def __init__(self, host: str = "127.0.0.1", port: int = DASHBOARD_PORT) -> None:
        self.host = host
        self.port = port
        self._server = None
        self._thread: Thread | None = None
        self._registry_path: str = ""

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        import os

        registry = session_registry_path()
        self._registry_path = str(registry)
        app = create_app()
        app.config["SESSION_REGISTRY_PATH"] = self._registry_path
        bridge_url = os.environ.get("BRIDGE_BASE_URL", "").strip() or default_bridge_base_url()
        app.config["BRIDGE_BASE_URL"] = bridge_url
        self._server = make_server(self.host, self.port, app, threaded=True)
        self._thread = Thread(target=self._server.serve_forever, name="career-copilot-flask", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None


class CareerCopilotLauncher:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.flask_runtime = FlaskRuntime(host="127.0.0.1", port=DASHBOARD_PORT)
        self.mobile_bridge: MobileBridgeServer | None = None
        self.tray = QSystemTrayIcon(self._build_icon(), self.app)

        self._configure_tray()

    def _configure_tray(self) -> None:
        menu = QMenu()

        open_action = QAction("Open Dashboard", self.app)
        open_action.triggered.connect(self._open_dashboard)
        menu.addAction(open_action)

        exit_action = QAction("Exit Career Copilot", self.app)
        exit_action.triggered.connect(self.shutdown)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Career Copilot Premium")
        self.tray.activated.connect(self._handle_tray_activated)

    @staticmethod
    def _build_icon() -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#0a0a0a"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#6366f1"))
        painter.drawText(pixmap.rect(), 0x84, "CC")
        painter.end()
        return QIcon(pixmap)

    def _open_dashboard(self) -> None:
        webbrowser.open(self.flask_runtime.url)

    def _handle_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_dashboard()

    def start_services(self) -> None:
        import os

        configure_runtime_environment()
        registry = session_registry_path()

        try:
            self.mobile_bridge = start_mobile_bridge_server(
                host="0.0.0.0",
                port=MOBILE_BRIDGE_PORT,
                registry_path=registry,
            )
            os.environ["BRIDGE_BASE_URL"] = self.mobile_bridge.url
        except OSError as error:
            print(f"[launcher] Mobile bridge unavailable: {error}")
            self.mobile_bridge = None

        self.flask_runtime.start()

        _wait_for_dashboard("127.0.0.1", DASHBOARD_PORT)
        self.tray.show()
        self._open_dashboard()

    def shutdown(self) -> None:
        try:
            if self.mobile_bridge is not None:
                self.mobile_bridge.stop()
                self.mobile_bridge = None
        finally:
            self.flask_runtime.stop()
            self.tray.hide()
            self.app.quit()

    def run(self) -> int:
        self.start_services()
        return self.app.exec()


def main() -> int:
    launcher = CareerCopilotLauncher()
    return launcher.run()


if __name__ == "__main__":
    raise SystemExit(main())
