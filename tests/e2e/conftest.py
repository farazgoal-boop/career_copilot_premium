"""Pytest fixtures: start the Flask server in a thread and provide a base URL."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup so imports work regardless of how pytest is invoked
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Port intentionally different from the app default (5000) to avoid conflicts
TEST_PORT = 5099


@pytest.fixture(scope="session")
def test_data_dir():
    """Isolated temp directory used as DATA_ROOT for the entire test session."""
    # ignore_cleanup_errors=True prevents Windows PermissionError when a worker
    # thread still holds a JSON file open at teardown time.
    with tempfile.TemporaryDirectory(prefix="ccp_e2e_", ignore_cleanup_errors=True) as tmp:
        yield Path(tmp)


@pytest.fixture(scope="session")
def live_server(test_data_dir):
    """Start the Flask app in a background thread and return its base URL."""
    os.environ["DATA_ROOT"] = str(test_data_dir)
    os.environ.pop("CCP_REQUIRE_LICENSE", None)   # bypass license gate

    # Import after env vars are set
    from werkzeug.serving import make_server
    from web_app.app import create_app

    app = create_app()
    app.config["TESTING"] = True

    server = make_server("127.0.0.1", TEST_PORT, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Wait for the server to be ready
    import urllib.request
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{TEST_PORT}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.15)

    yield f"http://127.0.0.1:{TEST_PORT}"

    server.shutdown()


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server


# ---------------------------------------------------------------------------
# Seed a test profile before any page tests run
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def seeded_profile(live_server, test_data_dir):
    """POST to /onboarding to create a profile via the real form handler."""
    import urllib.parse
    import urllib.request

    url = f"{live_server}/onboarding?response_format=json"
    data = urllib.parse.urlencode(
        {
            "full_name": "E2E Test User",
            "target_name": "Software Engineer",
            "current_role": "Junior Developer",
            "product_description": "Automated E2E test profile — no real resume needed.",
        }
    ).encode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            import json
            payload = json.loads(resp.read())
            return payload
    except Exception as exc:
        # If JSON decode fails, that's OK — the profile may still have been created
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def ss(page, name: str) -> None:
    """Save a screenshot to tests/e2e/screenshots/<name>.png."""
    page.screenshot(path=str(SCREENSHOTS_DIR / f"{name}.png"), full_page=True)
