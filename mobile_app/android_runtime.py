"""Android floating-bubble runtime scaffold built on the shared mobile contract."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import MobileBridgeSnapshot


@dataclass(frozen=True)
class AndroidPermission:
    name: str
    rationale: str


@dataclass(frozen=True)
class AndroidBubbleRuntimePlan:
    package_name: str
    min_sdk: int
    foreground_service_name: str
    settings_activity_name: str
    bridge_source_version: str
    required_permissions: list[AndroidPermission]
    initial_snapshot: dict[str, object]


def build_android_runtime_plan(snapshot: MobileBridgeSnapshot) -> AndroidBubbleRuntimePlan:
    permissions = [
        AndroidPermission("SYSTEM_ALERT_WINDOW", "Draw the floating bubble above other apps."),
        AndroidPermission("FOREGROUND_SERVICE", "Keep the bubble and microphone controls alive."),
        AndroidPermission("POST_NOTIFICATIONS", "Show foreground-service and answer-ready alerts."),
        AndroidPermission("RECORD_AUDIO", "Allow future mobile-side microphone capture support."),
    ]
    return AndroidBubbleRuntimePlan(
        package_name="com.careercopilot.premium",
        min_sdk=29,
        foreground_service_name="CareerCopilotBubbleService",
        settings_activity_name="CareerCopilotSettingsActivity",
        bridge_source_version=snapshot.source_version,
        required_permissions=permissions,
        initial_snapshot=snapshot.to_dict(),
    )