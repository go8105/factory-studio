from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def new_session_token(kind: str) -> str:
    if kind not in {"g", "m"}:
        raise ValueError("unknown session kind")
    return f"{kind}_{secrets.token_urlsafe(32)}"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def guest_csrf_token(secret: str, token: str) -> str:
    return hmac.new(
        secret.encode(), f"csrf:{token}".encode(), hashlib.sha256
    ).hexdigest()


def member_csrf_token(secret: str, token: str) -> str:
    return hmac.new(
        secret.encode(), f"member-csrf:{token}".encode(), hashlib.sha256
    ).hexdigest()


def csrf_matches(secret: str, token: str, supplied: str) -> bool:
    return hmac.compare_digest(guest_csrf_token(secret, token), supplied)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return (
        "scrypt$16384$8$1$"
        + base64.urlsafe_b64encode(salt).decode()
        + "$"
        + base64.urlsafe_b64encode(digest).decode()
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        name, n, r, p, salt_text, digest_text = encoded.split("$")
        if name != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.scrypt(
            password.encode(), salt=salt, n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(actual, expected)
    except ValueError, TypeError:
        return False
