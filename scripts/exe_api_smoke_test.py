"""Quick API smoke test for built EXE (no Playwright browser needed)."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5000"


def call(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"error": str(exc)}
        return exc.code, payload


def main() -> int:
    passed: list[str] = []
    stamp = str(int(time.time()))[-6:]

    status, health = call("/api/health")
    assert status == 200 and health.get("status") == "ok", f"health failed: {status} {health}"
    passed.append("health")

    status, lic = call("/api/license/status")
    assert status == 200, f"license status failed: {status} {lic}"
    passed.append("license_status")
    if not lic.get("activated"):
        print("WARN: machine not activated — some tests may fail")

    briefing = {
        "session_id": f"exe-smoke-{stamp}-acme-ai-{stamp}-staff-backend-engineer",
        "full_name": f"EXE Smoke {stamp}",
        "current_role": "Senior Python Developer",
        "strongest_skill": "Python backend development",
        "project_technologies": "Python, FastAPI, PostgreSQL",
        "target_role": "Staff Backend Engineer",
        "company_name": f"Acme AI {stamp}",
        "answer_style": "Simple English, concise, confident",
        "expected_questions": "What is your experience with Python?\nWhy should we hire you?",
        "resume_text": "4 years Python backend. Built APIs and improved performance by 35%.",
    }
    status, saved = call("/api/briefing", method="POST", body=briefing)
    session_id = str(saved.get("session_id") or briefing["session_id"])
    assert status == 200 and session_id, f"briefing failed: {status} {saved}"
    passed.append("briefing_save")

    question = "What is your experience with Python backend development?"
    status, answer = call(f"/api/session/{session_id}/transcript", method="POST", body={"transcript": question})
    assert status == 200 and answer.get("ok"), f"transcript failed: {status} {answer}"
    text = str(answer.get("suggested_answer", ""))
    assert len(text) > 20, f"answer too short: {text}"
    lower = text.lower()
    assert any(word in lower for word in ("python", "backend", "api", "develop", "experience")), (
        f"answer not relevant: {text[:200]}"
    )
    passed.append("transcript_answer")

    status, snap = call(f"/api/session/{session_id}")
    assert status == 200, f"snapshot failed: {status} {snap}"
    headline = str(snap.get("overlay", {}).get("headline", ""))
    body = str(snap.get("overlay", {}).get("body", ""))
    for label, value in ("headline", headline), ("body", body):
        assert "\ufffd" not in value, f"{label} has tofu: {value}"
    passed.append("live_dock_snapshot")

    print(json.dumps({
        "ok": True,
        "base_url": BASE,
        "session_id": session_id,
        "license_activated": lic.get("activated"),
        "provider": answer.get("provider_status"),
        "answer_preview": text[:220],
        "passed": passed,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
