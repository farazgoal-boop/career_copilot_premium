"""Encryption helpers for saved session artifacts."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from runtime_paths import cache_root, resolve_data_root

try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover - packaged fallback when cryptography is unavailable
    Fernet = None


ENCRYPTION_PREFIX = "enc:v1:"
ENCRYPTED_JSON_MARKER = "career_copilot_encrypted_v1"
DEFAULT_KEY_FILENAME = "session_artifacts.key"


def default_encryption_key_path() -> Path:
    return cache_root(resolve_data_root()) / DEFAULT_KEY_FILENAME


def load_or_create_encryption_key(path: str | Path | None = None) -> bytes:
    key_path = Path(path) if path is not None else default_encryption_key_path()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_bytes().strip()

    if Fernet is None:
        key = base64.urlsafe_b64encode(os.urandom(32))
    else:
        key = Fernet.generate_key()
    key_path.write_bytes(key)
    return key


def encrypt_text(plain_text: str, key_path: str | Path | None = None) -> str:
    if Fernet is None:
        encoded = base64.urlsafe_b64encode(plain_text.encode("utf-8")).decode("utf-8")
        return ENCRYPTION_PREFIX + "plain:" + encoded
    fernet = Fernet(load_or_create_encryption_key(key_path))
    token = fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
    return ENCRYPTION_PREFIX + token


def decrypt_text(cipher_text: str, key_path: str | Path | None = None) -> str:
    if not cipher_text.startswith(ENCRYPTION_PREFIX):
        return cipher_text
    if Fernet is None:
        payload = cipher_text[len(ENCRYPTION_PREFIX):]
        if payload.startswith("plain:"):
            encoded = payload[len("plain:"):]
            return base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8")
        return payload
    fernet = Fernet(load_or_create_encryption_key(key_path))
    token = cipher_text[len(ENCRYPTION_PREFIX):].encode("utf-8")
    return fernet.decrypt(token).decode("utf-8")


def encrypt_json_payload(payload: dict[str, object], key_path: str | Path | None = None) -> str:
    return encrypt_text(json.dumps(payload), key_path)


def decrypt_json_payload(cipher_text: str, key_path: str | Path | None = None) -> dict[str, object]:
    return json.loads(decrypt_text(cipher_text, key_path))


def write_encrypted_json_file(path: str | Path, payload: dict[str, object], key_path: str | Path | None = None) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = {
        "format": ENCRYPTED_JSON_MARKER,
        "payload": encrypt_json_payload(payload, key_path),
    }
    file_path.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
    return file_path


def read_encrypted_json_file(path: str | Path, key_path: str | Path | None = None) -> dict[str, object]:
    wrapper = json.loads(Path(path).read_text(encoding="utf-8"))
    if wrapper.get("format") != ENCRYPTED_JSON_MARKER:
        return wrapper
    return decrypt_json_payload(str(wrapper["payload"]), key_path)