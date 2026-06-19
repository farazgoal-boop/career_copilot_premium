"""Android foreground-service loop for the Kivy mobile prototype."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mobile_app.android_native import default_android_service_state_path, read_android_service_state, write_android_service_state
from mobile_app.live_bridge import build_live_bridge_payload
from mobile_app.runtime_bridge import load_mobile_bridge_snapshot


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_overlay_payload(bridge_source: str) -> dict[str, object]:
    if not bridge_source:
        return {}
    if bridge_source.startswith("http://") or bridge_source.startswith("https://"):
        payload = json.loads(urlopen(bridge_source).read().decode("utf-8"))
        return dict(payload.get("overlay", {})) if isinstance(payload, dict) else {}

    snapshot = load_mobile_bridge_snapshot(Path(bridge_source))
    payload = build_live_bridge_payload(snapshot)
    overlay = payload.get("overlay", {})
    return dict(overlay) if isinstance(overlay, dict) else {}


def run_service_loop() -> None:
    bridge_path = os.environ.get("CAREER_COPILOT_MOBILE_BRIDGE_URL") or os.environ.get("CAREER_COPILOT_MOBILE_BRIDGE", "")
    state_path = default_android_service_state_path()
    initial_state = read_android_service_state(state_path)
    initial_state.update(
        {
            "running": True,
            "bridge_path": bridge_path,
            "bridge_source": bridge_path,
            "service_name": "CareerCopilotBubbleService",
            "last_heartbeat_at": _utc_now_iso(),
        }
    )
    write_android_service_state(state_path, initial_state)

    try:
        while True:
            current_state = read_android_service_state(state_path)
            try:
                overlay_payload = _load_overlay_payload(bridge_path)
                current_state["overlay"] = overlay_payload
                current_state.pop("last_error", None)
            except Exception as error:
                current_state["last_error"] = str(error)
            current_state.update(
                {
                    "running": True,
                    "bridge_path": bridge_path,
                    "bridge_source": bridge_path,
                    "service_name": "CareerCopilotBubbleService",
                    "last_heartbeat_at": _utc_now_iso(),
                }
            )
            write_android_service_state(state_path, current_state)
            time.sleep(5.0)
    finally:
        current_state = read_android_service_state(state_path)
        current_state.update({"running": False, "last_heartbeat_at": _utc_now_iso()})
        write_android_service_state(state_path, current_state)


if __name__ == "__main__":
    run_service_loop()