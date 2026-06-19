"""Offline machine-bound licensing helpers for packaged desktop installs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import re
import uuid

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback.
    winreg = None


APP_STORAGE_DIRNAME = "CareerCopilotPremium"
LICENSE_FILENAME = "license_state.json"
ACTIVATION_SECRET = b"career-copilot-premium-offline-license-v1"


def license_storage_dir() -> Path:
    try:
        from runtime_paths import cache_root, is_portable_mode, repo_root, resolve_data_root

        if is_portable_mode() or resolve_data_root().resolve() == repo_root().resolve():
            return cache_root()
    except ImportError:
        pass

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        root = Path(local_app_data)
    else:
        root = Path.home()
    return root / APP_STORAGE_DIRNAME


def license_state_path() -> Path:
    return license_storage_dir() / LICENSE_FILENAME


def machine_name() -> str:
    return (
        os.environ.get("COMPUTERNAME", "").strip()
        or platform.node().strip()
        or "Unknown Windows PC"
    )


def machine_fingerprint() -> str:
    payload = "|".join(
        item
        for item in [
            _read_windows_machine_guid(),
            machine_name(),
            f"{uuid.getnode():012x}",
        ]
        if item
    )
    if not payload:
        payload = machine_name() or "career-copilot-premium"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()[:24]


def machine_request_code() -> str:
    digest = hashlib.sha256(f"REQUEST::{machine_fingerprint()}".encode("utf-8")).hexdigest().upper()[:20]
    return _format_code("CCP", digest)


def generate_activation_code(request_code: str) -> str:
    normalized_request_code = _normalize_code(request_code)
    if len(normalized_request_code) != 23 or not normalized_request_code.startswith("CCP"):
        raise ValueError("Request code format is invalid.")
    digest = hmac.new(ACTIVATION_SECRET, normalized_request_code.encode("utf-8"), hashlib.sha256).hexdigest().upper()[:20]
    return _format_code("ACT", digest)


def activate_machine_license(activation_code: str) -> dict[str, object]:
    normalized_activation_code = _normalize_code(activation_code)
    expected_code = _normalize_code(generate_activation_code(machine_request_code()))
    if normalized_activation_code != expected_code:
        raise ValueError("Activation code is invalid for this computer.")

    payload = {
        "activated": True,
        "machine_name": machine_name(),
        "machine_fingerprint": machine_fingerprint(),
        "request_code": machine_request_code(),
        "activation_code": _format_code("ACT", normalized_activation_code[3:]),
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = license_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return current_license_status()


def current_license_status() -> dict[str, object]:
    path = license_state_path()
    payload = _load_license_payload(path)
    current_fingerprint = machine_fingerprint()
    current_request_code = machine_request_code()
    activated = bool(
        payload.get("activated")
        and str(payload.get("machine_fingerprint", "")).upper() == current_fingerprint
        and _normalize_code(str(payload.get("request_code", ""))) == _normalize_code(current_request_code)
        and _normalize_code(str(payload.get("activation_code", "")))
        == _normalize_code(generate_activation_code(current_request_code))
    )
    return {
        "activated": activated,
        "machine_name": machine_name(),
        "machine_fingerprint": current_fingerprint,
        "request_code": current_request_code,
        "license_path": str(path),
        "activated_at": str(payload.get("activated_at", "")) if activated else "",
    }


def is_machine_licensed() -> bool:
    import sys

    require_license = os.environ.get("CCP_REQUIRE_LICENSE", "").strip().lower() in {"1", "true", "yes", "on"}
    if getattr(sys, "frozen", False):
        require_license = True
    if require_license:
        return bool(current_license_status().get("activated"))
    return True


def _load_license_payload(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_windows_machine_guid() -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value).strip()
    except OSError:
        return ""


def _normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _format_code(prefix: str, raw: str) -> str:
    normalized = _normalize_code(raw)
    groups = [normalized[index : index + 4] for index in range(0, len(normalized), 4)]
    return "-".join([prefix] + groups)