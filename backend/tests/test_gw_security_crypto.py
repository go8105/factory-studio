from datetime import UTC, datetime

import pyotp
import pytest
from cryptography.fernet import Fernet

from fs.common.errors import ApiError
from fs.common.security import hash_password, verify_password
from fs.core.security.config import security_settings
from fs.core.security.crypto import (
    SecretBox,
    enrollment,
    new_recovery_codes,
    opaque_token,
    throttle_bucket,
    totp_step,
)


def test_secret_ciphertext_bound_to_owner_purpose_and_key():
    box = SecretBox("v1", {"v1": Fernet.generate_key()})
    kid, sealed = box.seal("synthetic-secret", purpose="totp", owner="1")
    assert "synthetic-secret" not in sealed
    assert box.open(sealed, key_id=kid, purpose="totp", owner="1") == "synthetic-secret"
    for changes in (
        {"owner": "2"},
        {"purpose": "oidc"},
        {"key_id": "absent"},
        {"ciphertext": sealed[:-3] + "abc"},
    ):
        args = {
            "ciphertext": sealed,
            "key_id": kid,
            "purpose": "totp",
            "owner": "1",
        } | changes
        with pytest.raises(ApiError):
            box.open(**args)
    assert "synthetic-secret" not in repr(box)


def test_key_rotation_reads_old_ciphertext_and_writes_new():
    old, new = Fernet.generate_key(), Fernet.generate_key()
    _, sealed = SecretBox("old", {"old": old}).seal("seed", purpose="totp", owner="1")
    rotated = SecretBox("new", {"old": old, "new": new})
    assert rotated.open(sealed, key_id="old", purpose="totp", owner="1") == "seed"
    assert rotated.seal("seed", purpose="totp", owner="1")[0] == "new"


def test_totp_rfc6238_vector_window_replay_and_ascii_only():
    # RFC 6238 SHA1 test seed, reduced to the product's six digits.
    seed = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    now = datetime.fromtimestamp(59, UTC)
    assert totp_step(seed, "287082", now=now, last_used_step=None) == 1
    assert totp_step(seed, "287082", now=now, last_used_step=1) is None
    assert totp_step(seed, "２８７０８２", now=now, last_used_step=None) is None
    assert (
        totp_step(
            seed, "287082", now=datetime.fromtimestamp(120, UTC), last_used_step=None
        )
        is None
    )
    assert (
        totp_step(
            seed, "287082", now=datetime.fromtimestamp(89, UTC), last_used_step=None
        )
        == 1
    )


def test_enrollment_and_recovery_material():
    seed, uri = enrollment("synthetic-user")
    assert len(seed) >= 32 and pyotp.parse_uri(uri).secret == seed
    codes = new_recovery_codes()
    assert len(codes) == len(set(codes)) == 8
    assert all(len(c) == 32 for c in codes)
    hashed = hash_password(codes[0])
    assert codes[0] not in hashed and verify_password(codes[0], hashed)
    assert not verify_password(codes[1], hashed)
    token, hashed = opaque_token()
    assert len(token) >= 43 and len(hashed) == 64 and token != hashed


def test_throttle_namespace_and_secret_separation():
    a = throttle_bucket(b"a" * 32, namespace="account", value="person")
    assert "person" not in a
    assert a != throttle_bucket(b"a" * 32, namespace="network", value="person")
    assert a != throttle_bucket(b"b" * 32, namespace="account", value="person")


def test_company_configuration_fail_closed(monkeypatch):
    for key in (
        "FS_SECURITY_MODE",
        "FS_SECURITY_KEYS",
        "FS_SECURITY_KEY_ID",
        "FS_PUBLIC_ORIGIN",
        "COOKIE_SECURE",
    ):
        monkeypatch.delenv(key, raising=False)
    assert security_settings().mode == "PUBLIC_DEMO"
    monkeypatch.setenv("FS_SECURITY_MODE", "COMPANY")
    with pytest.raises(ApiError):
        security_settings()
    import json

    monkeypatch.setenv(
        "FS_SECURITY_KEYS", json.dumps({"v1": Fernet.generate_key().decode()})
    )
    monkeypatch.setenv("FS_SECURITY_KEY_ID", "v1")
    monkeypatch.setenv("FS_PUBLIC_ORIGIN", "https://gw.example.invalid")
    assert security_settings().box is not None
    for origin in (
        "http://gw.example.invalid",
        "https://user:pass@gw.example.invalid",
        "https://gw.example.invalid/path",
        "https://gw.example.invalid?token=x",
    ):
        monkeypatch.setenv("FS_PUBLIC_ORIGIN", origin)
        with pytest.raises(ApiError):
            security_settings()
    monkeypatch.setenv("FS_PUBLIC_ORIGIN", "https://gw.example.invalid")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    with pytest.raises(ApiError):
        security_settings()
