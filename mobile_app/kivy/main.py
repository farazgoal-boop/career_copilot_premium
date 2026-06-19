"""Kivy mobile dashboard for exported bridge snapshots and local control actions."""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mobile_app.contracts import MobileBridgeSnapshot
from mobile_app.android_native import (
    AndroidEnvironmentStatus,
    build_android_environment_status,
    request_android_runtime_access,
    start_android_bubble_service,
    stop_android_bubble_service,
)
from mobile_app.android_runtime import build_android_runtime_plan
from mobile_app.runtime_bridge import enqueue_mobile_bridge_action, load_mobile_bridge_snapshot

try:
    from kivy.app import App
    from kivy.lang import Builder
    from kivy.properties import StringProperty

    KIVY_AVAILABLE = True
except ImportError:
    App = object
    Builder = None
    StringProperty = None
    KIVY_AVAILABLE = False


DEFAULT_MOBILE_BRIDGE_PATH = REPO_ROOT / "mobile_bridge.json"


def load_dashboard_snapshot(path: str | Path | None = None) -> MobileBridgeSnapshot:
    snapshot_path = Path(path) if path is not None else DEFAULT_MOBILE_BRIDGE_PATH
    return load_mobile_bridge_snapshot(snapshot_path)


def build_mobile_dashboard_summary(snapshot: MobileBridgeSnapshot) -> str:
    action_labels = ", ".join(action.label for action in snapshot.actions)
    return (
        f"Session: {snapshot.session_id}\n"
        f"Company: {snapshot.company_name}\n"
        f"Role: {snapshot.role_title}\n"
        f"Status: {snapshot.bubble.status}\n"
        f"Headline: {snapshot.bubble.headline}\n"
        f"Body: {snapshot.bubble.body}\n"
        f"Actions: {action_labels or 'None'}"
    )


def enqueue_dashboard_action(
    snapshot: MobileBridgeSnapshot,
    action_id: str,
    registry_path: str | Path | None = None,
) -> Path:
    return enqueue_mobile_bridge_action(snapshot, action_id, registry_path)


if KIVY_AVAILABLE:
    KV_LAYOUT = """
BoxLayout:
    orientation: 'vertical'
    padding: 16
    spacing: 12

    Label:
        text: app.header_text
        text_size: self.width, None
        halign: 'left'
        valign: 'middle'
        size_hint_y: None
        height: self.texture_size[1] + 8

    Label:
        text: app.body_text
        text_size: self.width, None
        halign: 'left'
        valign: 'top'

    Label:
        text: app.permissions_text
        text_size: self.width, None
        halign: 'left'
        valign: 'top'
        size_hint_y: None
        height: self.texture_size[1] + 8

    Label:
        text: app.service_text
        text_size: self.width, None
        halign: 'left'
        valign: 'top'
        size_hint_y: None
        height: self.texture_size[1] + 8

    GridLayout:
        cols: 2
        size_hint_y: None
        height: self.minimum_height
        spacing: 8

        Button:
            text: 'Refresh'
            on_press: app.refresh_snapshot()
        Button:
            text: 'Toggle Mic'
            on_press: app.handle_action('toggle')
        Button:
            text: 'Grant Access'
            on_press: app.handle_permission_access()
        Button:
            text: 'Simple'
            on_press: app.handle_action('fallback_simple')
        Button:
            text: 'Start Service'
            on_press: app.handle_start_service()
        Button:
            text: 'Emergency'
            on_press: app.handle_action('fallback_emergency')
        Button:
            text: 'Stop Service'
            on_press: app.handle_stop_service()
        Button:
            text: 'Stop Worker'
            on_press: app.handle_action('stop_worker')
        Button:
            text: 'Status'
            on_press: app.handle_action('status')

    Label:
        text: app.last_result_text
        text_size: self.width, None
        halign: 'left'
        valign: 'top'
        size_hint_y: None
        height: self.texture_size[1] + 8
"""


    class CareerCopilotMobileApp(App):
        header_text = StringProperty("Career Copilot Mobile")
        body_text = StringProperty("Load a mobile bridge snapshot to start.")
        permissions_text = StringProperty("")
        service_text = StringProperty("")
        last_result_text = StringProperty("No action queued yet.")

        def __init__(self, snapshot_path: str | Path | None = None, registry_path: str | Path | None = None, android_bridge: object | None = None, service_state_path: str | Path | None = None, **kwargs: object) -> None:
            super().__init__(**kwargs)
            self.snapshot_path = Path(snapshot_path) if snapshot_path is not None else DEFAULT_MOBILE_BRIDGE_PATH
            self.registry_path = Path(registry_path) if registry_path is not None else None
            self.android_bridge = android_bridge
            self.service_state_path = Path(service_state_path) if service_state_path is not None else None
            self.snapshot: MobileBridgeSnapshot | None = None
            self.android_status: AndroidEnvironmentStatus | None = None

        def build(self):
            self.title = "Career Copilot Mobile"
            self.refresh_snapshot()
            return Builder.load_string(KV_LAYOUT)

        def refresh_snapshot(self) -> None:
            try:
                self.snapshot = load_dashboard_snapshot(self.snapshot_path)
                self.header_text = f"{self.snapshot.company_name} | {self.snapshot.role_title}"
                self.body_text = build_mobile_dashboard_summary(self.snapshot)
                self._refresh_android_status()
                self.last_result_text = f"Loaded snapshot from {self.snapshot_path}"
            except FileNotFoundError:
                self.snapshot = None
                self.header_text = "Career Copilot Mobile"
                self.body_text = f"Snapshot not found: {self.snapshot_path}"
                self.permissions_text = "Export a bridge file with --export-mobile-bridge first."
                self.service_text = "Android service controls unavailable until a snapshot is loaded."
                self.last_result_text = "Waiting for mobile bridge snapshot."

        def handle_action(self, action_id: str) -> None:
            if self.snapshot is None:
                self.last_result_text = "No snapshot loaded."
                return

            try:
                queue_path = enqueue_dashboard_action(self.snapshot, action_id, self.registry_path)
                self.last_result_text = f"Queued {action_id} to {queue_path}"
            except ValueError as error:
                self.last_result_text = str(error)

        def handle_permission_access(self) -> None:
            if self.snapshot is None:
                self.last_result_text = "No snapshot loaded."
                return
            plan = build_android_runtime_plan(self.snapshot)
            self.last_result_text = request_android_runtime_access(plan, bridge=self.android_bridge)
            self._refresh_android_status()

        def handle_start_service(self) -> None:
            if self.snapshot is None:
                self.last_result_text = "No snapshot loaded."
                return
            plan = build_android_runtime_plan(self.snapshot)
            self.last_result_text = start_android_bubble_service(
                plan,
                bridge_snapshot_path=self.snapshot_path,
                bridge=self.android_bridge,
                service_state_path=self.service_state_path,
            )
            self._refresh_android_status()

        def handle_stop_service(self) -> None:
            if self.snapshot is None:
                self.last_result_text = "No snapshot loaded."
                return
            plan = build_android_runtime_plan(self.snapshot)
            self.last_result_text = stop_android_bubble_service(
                plan,
                bridge=self.android_bridge,
                service_state_path=self.service_state_path,
            )
            self._refresh_android_status()

        def _refresh_android_status(self) -> None:
            if self.snapshot is None:
                self.permissions_text = ""
                self.service_text = ""
                return
            plan = build_android_runtime_plan(self.snapshot)
            self.android_status = build_android_environment_status(
                plan,
                bridge=self.android_bridge,
                service_state_path=self.service_state_path,
            )
            self.permissions_text = (
                f"Overlay: {'yes' if self.android_status.overlay_permission_granted else 'no'} | "
                f"Notifications: {'yes' if self.android_status.notification_permission_granted else 'no'} | "
                f"Microphone: {'yes' if self.android_status.microphone_permission_granted else 'no'}"
            )
            self.service_text = (
                f"Service running: {'yes' if self.android_status.foreground_service_running else 'no'} | "
                f"{self.android_status.status_message}"
            )


    def launch_mobile_dashboard(snapshot_path: str | Path | None = None, registry_path: str | Path | None = None, android_bridge: object | None = None, service_state_path: str | Path | None = None) -> int:
        CareerCopilotMobileApp(
            snapshot_path=snapshot_path,
            registry_path=registry_path,
            android_bridge=android_bridge,
            service_state_path=service_state_path,
        ).run()
        return 0

else:
    def launch_mobile_dashboard(snapshot_path: str | Path | None = None, registry_path: str | Path | None = None, android_bridge: object | None = None, service_state_path: str | Path | None = None) -> int:
        raise RuntimeError("Kivy is required to launch the mobile dashboard. Install it in the Android/mobile environment.")


if __name__ == "__main__":
    snapshot_path = Path(os.environ.get("CAREER_COPILOT_MOBILE_BRIDGE", DEFAULT_MOBILE_BRIDGE_PATH))
    registry_override = os.environ.get("CAREER_COPILOT_SESSION_REGISTRY")
    raise SystemExit(launch_mobile_dashboard(snapshot_path=snapshot_path, registry_path=registry_override))