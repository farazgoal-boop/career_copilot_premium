"""SSE helpers for the live web dashboard."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Iterator


def build_session_event(
    session_id: str,
    registry_path: str | Path | None = None,
    base_url: str | None = None,
) -> str:
    from mobile_app.live_bridge import build_live_bridge_payload_for_session

    payload = build_live_bridge_payload_for_session(session_id, registry_path=registry_path, base_url=base_url)
    return "event: snapshot\n" + "data: " + json.dumps(payload) + "\n\n"


def stream_session_events(
    session_id: str,
    registry_path: str | Path | None = None,
    base_url: str | None = None,
    poll_interval: float = 1.5,
    heartbeat_interval: float = 15.0,
) -> Iterator[str]:
    from mobile_app.live_bridge import build_live_bridge_payload_for_session

    last_payload = ""
    last_sent_at = 0.0
    while True:
        payload = build_live_bridge_payload_for_session(session_id, registry_path=registry_path, base_url=base_url)
        encoded_payload = json.dumps(payload, sort_keys=True)
        now = time.monotonic()
        if encoded_payload != last_payload:
            yield "event: snapshot\n" + "data: " + encoded_payload + "\n\n"
            last_payload = encoded_payload
            last_sent_at = now
        elif now - last_sent_at >= heartbeat_interval:
            yield "event: heartbeat\n" + "data: {}\n\n"
            last_sent_at = now
        time.sleep(poll_interval)