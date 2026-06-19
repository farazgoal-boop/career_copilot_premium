"""Career Copilot mobile bridge and Android runtime scaffolding."""

from .android_native import (
    AndroidEnvironmentStatus,
    build_android_environment_status,
    request_android_runtime_access,
    start_android_bubble_service,
    stop_android_bubble_service,
)
from .android_runtime import AndroidBubbleRuntimePlan, AndroidPermission, build_android_runtime_plan
from .contracts import MobileBridgeAction, MobileBridgeSnapshot, MobileBubbleState
from .kivy.main import build_mobile_dashboard_summary, enqueue_dashboard_action, launch_mobile_dashboard, load_dashboard_snapshot
from .runtime_bridge import (
    build_mobile_bridge_snapshot,
    build_mobile_bridge_snapshot_for_session,
    enqueue_mobile_bridge_action,
    export_mobile_bridge_snapshot,
    load_mobile_bridge_snapshot,
)

__all__ = [
    "AndroidEnvironmentStatus",
    "AndroidBubbleRuntimePlan",
    "AndroidPermission",
    "MobileBridgeAction",
    "MobileBridgeSnapshot",
    "MobileBubbleState",
    "build_android_runtime_plan",
    "build_android_environment_status",
    "build_mobile_dashboard_summary",
    "build_mobile_bridge_snapshot",
    "build_mobile_bridge_snapshot_for_session",
    "enqueue_dashboard_action",
    "enqueue_mobile_bridge_action",
    "export_mobile_bridge_snapshot",
    "launch_mobile_dashboard",
    "load_dashboard_snapshot",
    "load_mobile_bridge_snapshot",
    "request_android_runtime_access",
    "start_android_bubble_service",
    "stop_android_bubble_service",
]