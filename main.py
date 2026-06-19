"""Buildozer entrypoint for the mobile Kivy dashboard."""

from __future__ import annotations

import os
from pathlib import Path

from mobile_app.kivy.main import DEFAULT_MOBILE_BRIDGE_PATH, launch_mobile_dashboard


if __name__ == "__main__":
    snapshot_path = Path(os.environ.get("CAREER_COPILOT_MOBILE_BRIDGE", DEFAULT_MOBILE_BRIDGE_PATH))
    registry_override = os.environ.get("CAREER_COPILOT_SESSION_REGISTRY")
    raise SystemExit(launch_mobile_dashboard(snapshot_path=snapshot_path, registry_path=registry_override))