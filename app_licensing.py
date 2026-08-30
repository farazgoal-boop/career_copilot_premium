"""Offline, machine-bound license verification using Ed25519 signatures.

Flow: the app derives a REQUEST CODE from a stable per-machine fingerprint and
shows it to the user, who sends it to the seller. The seller runs
scripts/generate_activation_code.py (which holds the ONLY copy of the private
key, kept entirely outside this repo, never shipped) to sign that exact string,
producing an ACTIVATION CODE unique to that one machine. This module verifies
that signature using only the embedded PUBLIC key -- a public key reveals
nothing that lets anyone forge a new signature or activate a different machine.

This replaces the previous shared-secret HMAC scheme (ACTIVATION_SECRET, a
single string that both signed and verified, compiled into every shipped
build -- recoverable by decompiling the app and reusable to mint codes for
any machine). Mirrors the same request/activation-code shape used by the
sibling products JobMind Match and MessageCannon.

This module must never import or reference a private key. If a private key
ever needs to be loaded, that belongs in scripts/generate_activation_code.py
only.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback.
    winreg = None


APP_STORAGE_DIRNAME = "CareerCopilotPremium"
LICENSE_FILENAME = "license_state.json"

REQUEST_PREFIX = "CCP"
ACTIVATION_PREFIX = "ACT"
_SIGNATURE_LEN = 64  # Ed25519 signatures are always exactly 64 bytes.

# Public key only -- generated once via `python scripts/generate_activation_code.py
# --init-keys`, which prints this value for pasting in here. Safe to embed: an
# Ed25519 public key cannot be used to derive the private key or forge a
# signature, only to verify one already produced by the matching private key.
PUBLIC_KEY_B64 = "S6IeU7Jq4rRvPpEqz7yn4JXM+1CTsovQdiQUbt56H3Q="


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
            _read_stable_machine_id(),
            machine_name(),
        ]
        if item
    )
    if not payload:
        payload = machine_name() or "career-copilot-premium"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()[:24]


def machine_request_code() -> str:
    """Not itself cryptographic material -- just a stable, human-shareable
    proxy for this machine's fingerprint. The seller signs this exact string;
    verification recomputes it locally and checks the signature against it, so
    a request code copied to a different machine won't produce a matching
    signature there."""
    digest = hashlib.sha256(f"REQUEST::{machine_fingerprint()}".encode("utf-8")).hexdigest().upper()[:20]
    return _format_code(REQUEST_PREFIX, digest)


def _b32_encode_signature(signature: bytes) -> str:
    return base64.b32encode(signature).decode("ascii").rstrip("=")


def _b32_decode_signature(encoded: str) -> bytes:
    # base32 requires the input length padded up to a multiple of 8.
    padded = encoded + "=" * (-len(encoded) % 8)
    return base64.b32decode(padded)


def format_activation_code(signature: bytes) -> str:
    if len(signature) != _SIGNATURE_LEN:
        raise ValueError(f"Expected a {_SIGNATURE_LEN}-byte Ed25519 signature")
    return _format_code(ACTIVATION_PREFIX, _b32_encode_signature(signature))


def verify_activation_code(request_code: str, activation_code: str) -> bool:
    """True only if activation_code is a valid Ed25519 signature (by the
    embedded public key) over the exact request_code string. Never raises --
    malformed input, a tampered code, and a genuinely wrong signature are all
    just "not valid", since this sits directly in the untrusted activation
    request path."""
    try:
        normalized_activation = _normalize_code(activation_code)
        if not normalized_activation.startswith(ACTIVATION_PREFIX):
            return False
        raw = normalized_activation[len(ACTIVATION_PREFIX):]
        signature = _b32_decode_signature(raw)
        if len(signature) != _SIGNATURE_LEN:
            return False
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64))
        public_key.verify(signature, _normalize_code(request_code).encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
    except Exception:
        # Any other decode/library failure on attacker-controlled input is
        # still just "not a valid code", not a crash.
        return False


def activate_machine_license(activation_code: str) -> dict[str, object]:
    request_code = machine_request_code()
    if not verify_activation_code(request_code, activation_code):
        raise ValueError("Activation code is invalid for this computer.")

    normalized_activation_code = _normalize_code(activation_code)
    payload = {
        "activated": True,
        "machine_name": machine_name(),
        "machine_fingerprint": machine_fingerprint(),
        "request_code": request_code,
        "activation_code": _format_code(
            ACTIVATION_PREFIX, normalized_activation_code[len(ACTIVATION_PREFIX):]
        ),
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
        and verify_activation_code(current_request_code, str(payload.get("activation_code", "")))
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


def _read_stable_machine_id() -> str:
    system = platform.system()
    if system == "Windows":
        return _read_windows_machine_guid()
    if system == "Darwin":
        return _read_mac_platform_uuid()
    if system == "Linux":
        return _read_linux_machine_id()
    return ""


def _read_windows_machine_guid() -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value).strip()
    except OSError:
        return ""


def _read_mac_platform_uuid() -> str:
    try:
        output = subprocess.check_output(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8", errors="ignore")
    except (OSError, subprocess.SubprocessError):
        return ""
    match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', output)
    return match.group(1).strip() if match else ""


def _read_linux_machine_id() -> str:
    for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return ""


def _normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _format_code(prefix: str, raw: str) -> str:
    normalized = _normalize_code(raw)
    groups = [normalized[index : index + 4] for index in range(0, len(normalized), 4)]
    return "-".join([prefix] + groups)
