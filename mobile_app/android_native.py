"""Android-native permission and foreground-service helpers for the mobile dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Protocol

from .android_runtime import AndroidBubbleRuntimePlan


REPO_ROOT = Path(__file__).resolve().parents[1]
ANDROID_SERVICE_STATE_FILENAME = "android_service_state.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class AndroidEnvironmentStatus:
    platform_supported: bool
    overlay_permission_granted: bool
    notification_permission_granted: bool
    microphone_permission_granted: bool
    foreground_service_running: bool
    service_state_path: str
    status_message: str


class AndroidPlatformBridge(Protocol):
    @property
    def is_android(self) -> bool:
        ...

    def can_draw_overlays(self, package_name: str) -> bool:
        ...

    def check_permission(self, permission_name: str) -> bool:
        ...

    def request_permissions(self, permission_names: list[str]) -> None:
        ...

    def open_overlay_settings(self, package_name: str) -> None:
        ...

    def start_service(self, argument: str) -> None:
        ...

    def stop_service(self) -> None:
        ...


class DefaultAndroidPlatformBridge:
    def __init__(self) -> None:
        self._android_modules: dict[str, object] | None = None

    @property
    def is_android(self) -> bool:
        return self._load_android_modules() is not None

    def can_draw_overlays(self, package_name: str) -> bool:
        modules = self._require_android_modules()
        settings = modules["Settings"]
        activity = modules["PythonActivity"].mActivity
        return bool(settings.canDrawOverlays(activity))

    def check_permission(self, permission_name: str) -> bool:
        modules = self._require_android_modules()
        context_compat = modules["ContextCompat"]
        package_manager = modules["PackageManager"]
        activity = modules["PythonActivity"].mActivity
        manifest_permission = getattr(modules["ManifestPermission"], permission_name)
        return context_compat.checkSelfPermission(activity, manifest_permission) == package_manager.PERMISSION_GRANTED

    def request_permissions(self, permission_names: list[str]) -> None:
        modules = self._require_android_modules()
        requested = [getattr(modules["ManifestPermission"], name) for name in permission_names]
        modules["request_permissions"](requested)

    def open_overlay_settings(self, package_name: str) -> None:
        modules = self._require_android_modules()
        python_activity = modules["PythonActivity"]
        intent = modules["Intent"](modules["Settings"].ACTION_MANAGE_OVERLAY_PERMISSION)
        uri = modules["Uri"].parse(f"package:{package_name}")
        intent.setData(uri)
        python_activity.mActivity.startActivity(intent)

    def start_service(self, argument: str) -> None:
        modules = self._require_android_modules()
        modules["PythonService"].start(modules["PythonActivity"].mActivity, argument)

    def stop_service(self) -> None:
        modules = self._require_android_modules()
        modules["PythonService"].stop(modules["PythonActivity"].mActivity)

    def _require_android_modules(self) -> dict[str, object]:
        modules = self._load_android_modules()
        if modules is None:
            raise RuntimeError("Android runtime is not available in this environment.")
        return modules

    def _load_android_modules(self) -> dict[str, object] | None:
        if self._android_modules is not None:
            return self._android_modules

        if "ANDROID_ARGUMENT" not in os.environ:
            return None

        try:
            from android.permissions import request_permissions
            from jnius import autoclass

            self._android_modules = {
                "ContextCompat": autoclass("androidx.core.content.ContextCompat"),
                "Intent": autoclass("android.content.Intent"),
                "ManifestPermission": autoclass("android.Manifest$permission"),
                "PackageManager": autoclass("android.content.pm.PackageManager"),
                "PythonActivity": autoclass("org.kivy.android.PythonActivity"),
                "PythonService": autoclass("org.kivy.android.PythonService"),
                "Settings": autoclass("android.provider.Settings"),
                "Uri": autoclass("android.net.Uri"),
                "request_permissions": request_permissions,
            }
            return self._android_modules
        except Exception:
            return None


def default_android_service_state_path(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir) / ANDROID_SERVICE_STATE_FILENAME
    return REPO_ROOT / "data" / "cache" / ANDROID_SERVICE_STATE_FILENAME


def read_android_service_state(path: str | Path | None = None) -> dict[str, object]:
    state_path = Path(path) if path is not None else default_android_service_state_path()
    if not state_path.exists():
        return {
            "running": False,
            "started_at": "",
            "last_heartbeat_at": "",
            "bridge_path": "",
            "service_name": "",
        }
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_android_service_state(path: str | Path | None, payload: dict[str, object]) -> Path:
    state_path = Path(path) if path is not None else default_android_service_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return state_path


def build_android_environment_status(
    plan: AndroidBubbleRuntimePlan,
    bridge: AndroidPlatformBridge | None = None,
    service_state_path: str | Path | None = None,
) -> AndroidEnvironmentStatus:
    resolved_bridge = bridge or DefaultAndroidPlatformBridge()
    service_state = read_android_service_state(service_state_path)
    if not resolved_bridge.is_android:
        return AndroidEnvironmentStatus(
            platform_supported=False,
            overlay_permission_granted=False,
            notification_permission_granted=False,
            microphone_permission_granted=False,
            foreground_service_running=bool(service_state.get("running", False)),
            service_state_path=str(Path(service_state_path) if service_state_path is not None else default_android_service_state_path()),
            status_message="Android runtime unavailable; permission and service controls are disabled.",
        )

    overlay_granted = resolved_bridge.can_draw_overlays(plan.package_name)
    notification_granted = resolved_bridge.check_permission("POST_NOTIFICATIONS")
    microphone_granted = resolved_bridge.check_permission("RECORD_AUDIO")
    running = bool(service_state.get("running", False))
    return AndroidEnvironmentStatus(
        platform_supported=True,
        overlay_permission_granted=overlay_granted,
        notification_permission_granted=notification_granted,
        microphone_permission_granted=microphone_granted,
        foreground_service_running=running,
        service_state_path=str(Path(service_state_path) if service_state_path is not None else default_android_service_state_path()),
        status_message=(
            "Android controls ready."
            if overlay_granted and notification_granted and microphone_granted
            else "Android permissions still required before the bubble can run reliably."
        ),
    )


def request_android_runtime_access(
    plan: AndroidBubbleRuntimePlan,
    bridge: AndroidPlatformBridge | None = None,
) -> str:
    resolved_bridge = bridge or DefaultAndroidPlatformBridge()
    if not resolved_bridge.is_android:
        return "Android runtime unavailable; cannot request permissions from this environment."

    requested_permissions: list[str] = []
    for permission_name in ["POST_NOTIFICATIONS", "RECORD_AUDIO"]:
        if not resolved_bridge.check_permission(permission_name):
            requested_permissions.append(permission_name)

    if requested_permissions:
        resolved_bridge.request_permissions(requested_permissions)

    overlay_opened = False
    if not resolved_bridge.can_draw_overlays(plan.package_name):
        resolved_bridge.open_overlay_settings(plan.package_name)
        overlay_opened = True

    if not requested_permissions and not overlay_opened:
        return "Android access already granted."

    parts: list[str] = []
    if requested_permissions:
        parts.append("Requested permissions: " + ", ".join(requested_permissions))
    if overlay_opened:
        parts.append("Opened overlay permission settings")
    return "; ".join(parts)


def start_android_bubble_service(
    plan: AndroidBubbleRuntimePlan,
    bridge_snapshot_path: str | Path,
    bridge: AndroidPlatformBridge | None = None,
    service_state_path: str | Path | None = None,
) -> str:
    resolved_bridge = bridge or DefaultAndroidPlatformBridge()
    if not resolved_bridge.is_android:
        return "Android runtime unavailable; cannot start the foreground service from this environment."

    bridge_source = str(bridge_snapshot_path)
    if "://" not in bridge_source:
        bridge_source = str(Path(bridge_source))

    argument = f"--bridge={bridge_source}"
    resolved_bridge.start_service(argument)
    write_android_service_state(
        service_state_path,
        {
            "running": True,
            "started_at": _utc_now_iso(),
            "last_heartbeat_at": _utc_now_iso(),
            "bridge_path": bridge_source,
            "bridge_source": bridge_source,
            "service_name": plan.foreground_service_name,
        },
    )
    return f"Started Android foreground service: {plan.foreground_service_name}"


def stop_android_bubble_service(
    plan: AndroidBubbleRuntimePlan,
    bridge: AndroidPlatformBridge | None = None,
    service_state_path: str | Path | None = None,
) -> str:
    resolved_bridge = bridge or DefaultAndroidPlatformBridge()
    if not resolved_bridge.is_android:
        return "Android runtime unavailable; cannot stop the foreground service from this environment."

    resolved_bridge.stop_service()
    current_state = read_android_service_state(service_state_path)
    current_state.update(
        {
            "running": False,
            "last_heartbeat_at": _utc_now_iso(),
            "stopped_at": _utc_now_iso(),
            "service_name": plan.foreground_service_name,
        }
    )
    write_android_service_state(service_state_path, current_state)
    return f"Stopped Android foreground service: {plan.foreground_service_name}"