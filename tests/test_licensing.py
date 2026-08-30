"""Licensing tests for the Ed25519 machine-bound activation scheme.

Uses a throwaway, test-only Ed25519 keypair (never the real seller signing key
at ~/.career-copilot-license-signing/private_key.pem) so this suite never
depends on sensitive material outside the repo -- the same verification code
path is exercised regardless of whose key signed the message.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

import app_licensing


def _public_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def _sign(private_key: Ed25519PrivateKey, request_code: str) -> str:
    # Sign the NORMALIZED code (dashes stripped), same as
    # scripts/generate_activation_code.py -- verify_activation_code normalizes
    # before checking.
    signature = private_key.sign(app_licensing._normalize_code(request_code).encode("utf-8"))
    return app_licensing.format_activation_code(signature)


@pytest.fixture()
def throwaway_key(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(app_licensing, "PUBLIC_KEY_B64", _public_b64(private_key))
    return private_key


def test_request_code_is_stable_and_prefixed():
    code1 = app_licensing.machine_request_code()
    code2 = app_licensing.machine_request_code()
    assert code1 == code2
    assert code1.startswith("CCP-")


def test_machine_fingerprint_is_a_stable_hex_digest():
    fp1 = app_licensing.machine_fingerprint()
    fp2 = app_licensing.machine_fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 24
    assert all(c in "0123456789ABCDEF" for c in fp1)


def test_real_signature_over_the_real_request_code_verifies(throwaway_key):
    request_code = app_licensing.machine_request_code()
    activation_code = _sign(throwaway_key, request_code)
    assert activation_code.startswith("ACT-")
    assert app_licensing.verify_activation_code(request_code, activation_code) is True


def test_signature_for_a_different_request_code_does_not_verify(throwaway_key):
    activation_code = _sign(throwaway_key, app_licensing.machine_request_code())
    assert app_licensing.verify_activation_code("CCP-0000-0000-0000-0000-0000", activation_code) is False


def test_garbage_activation_codes_never_verify_and_never_raise(throwaway_key):
    request_code = app_licensing.machine_request_code()
    for bad in ["not-a-code", "", "ACT-", "ACT-" + "Z" * 200, None, 12345]:
        assert app_licensing.verify_activation_code(request_code, bad) is False  # type: ignore[arg-type]


def test_activation_code_signed_by_a_different_key_does_not_verify():
    real_key = Ed25519PrivateKey.generate()
    impostor_key = Ed25519PrivateKey.generate()
    original = app_licensing.PUBLIC_KEY_B64
    try:
        app_licensing.PUBLIC_KEY_B64 = _public_b64(real_key)
        request_code = app_licensing.machine_request_code()
        forged = _sign(impostor_key, request_code)
        assert app_licensing.verify_activation_code(request_code, forged) is False
    finally:
        app_licensing.PUBLIC_KEY_B64 = original


def test_format_activation_code_requires_a_real_ed25519_length_signature():
    with pytest.raises(ValueError):
        app_licensing.format_activation_code(b"too-short")


def test_activate_and_status_round_trip(throwaway_key, tmp_path, monkeypatch):
    monkeypatch.setattr(app_licensing, "license_storage_dir", lambda: tmp_path)

    request_code = app_licensing.machine_request_code()
    activation_code = _sign(throwaway_key, request_code)

    status = app_licensing.activate_machine_license(activation_code)
    assert status["activated"] is True
    assert app_licensing.license_state_path().exists()

    fresh = app_licensing.current_license_status()
    assert fresh["activated"] is True
    assert fresh["request_code"] == request_code


def test_status_is_inactive_before_activation(tmp_path, monkeypatch):
    monkeypatch.setattr(app_licensing, "license_storage_dir", lambda: tmp_path)
    status = app_licensing.current_license_status()
    assert status["activated"] is False
    assert status["request_code"].startswith("CCP-")


def test_activate_rejects_an_invalid_code(throwaway_key, tmp_path, monkeypatch):
    monkeypatch.setattr(app_licensing, "license_storage_dir", lambda: tmp_path)
    with pytest.raises(ValueError):
        app_licensing.activate_machine_license("ACT-NOT-A-REAL-SIGNATURE")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
