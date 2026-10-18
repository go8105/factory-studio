"""Secret handling with explicit key ownership. Never log returned enrollment values."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pyotp
from cryptography.fernet import Fernet, InvalidToken

from fs.common.errors import ApiError


def unavailable() -> ApiError:
    return ApiError(
        503, "SECURITY_CONFIGURATION_UNAVAILABLE", "보안 설정을 확인해 주세요."
    )


@dataclass(frozen=True)
class SecretBox:
    current_key_id: str
    keys: dict[str, bytes] = field(repr=False)

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", self.current_key_id):
            raise unavailable()
        try:
            if self.current_key_id not in self.keys or not self.keys:
                raise ValueError("missing key")
            for key_id, key in self.keys.items():
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", key_id):
                    raise ValueError("invalid key id")
                Fernet(key)
        except ValueError, TypeError:
            raise unavailable() from None

    def seal(self, plaintext: str, *, purpose: str, owner: str) -> tuple[str, str]:
        envelope = json.dumps(
            {"purpose": purpose, "owner": owner, "value": plaintext},
            separators=(",", ":"),
        ).encode()
        return self.current_key_id, Fernet(self.keys[self.current_key_id]).encrypt(
            envelope
        ).decode()

    def open(self, ciphertext: str, *, key_id: str, purpose: str, owner: str) -> str:
        try:
            raw = Fernet(self.keys[key_id]).decrypt(ciphertext.encode())
            value = json.loads(raw)
            if value["purpose"] != purpose or value["owner"] != owner:
                raise ValueError("wrong context")
            if not isinstance(value["value"], str):
                raise TypeError("wrong type")
            return value["value"]
        except KeyError, InvalidToken, ValueError, TypeError, UnicodeError:
            raise unavailable() from None


def enrollment(login_label: str) -> tuple[str, str]:
    secret = pyotp.random_base32()
    return secret, pyotp.TOTP(secret).provisioning_uri(
        name=login_label, issuer_name="Factory Studio"
    )


def totp_step(
    secret: str, code: str, *, now: datetime, last_used_step: int | None
) -> int | None:
    """Returns matching unused step. Caller MUST lock factor and persist step atomically."""
    if now.tzinfo is None:
        raise ValueError("timezone required")
    if not re.fullmatch(r"[0-9]{6}", code):
        return None
    step = int(now.timestamp()) // 30
    generator = pyotp.TOTP(secret)
    matches = [
        candidate
        for candidate in (step - 1, step, step + 1)
        if candidate >= 0
        and (last_used_step is None or candidate > last_used_step)
        and hmac.compare_digest(generator.at(candidate * 30), code)
    ]
    return max(matches) if matches else None


def new_recovery_codes() -> list[str]:
    # 128 random bits per code; display once. Hash with the existing scrypt adapter.
    return [secrets.token_hex(16) for _ in range(8)]


def opaque_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def throttle_bucket(secret: bytes, *, namespace: str, value: str) -> str:
    if len(secret) < 32 or namespace not in {"account", "network"}:
        raise unavailable()
    return hmac.new(secret, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)
