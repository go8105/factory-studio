"""Opt-in deployment configuration. Missing COMPANY secrets fail closed."""

import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from fs.core.security.crypto import SecretBox, unavailable


@dataclass(frozen=True)
class SecuritySettings:
    mode: str
    public_origin: str
    box: SecretBox | None = field(default=None, repr=False)


def security_settings() -> SecuritySettings:
    mode = os.environ.get("FS_SECURITY_MODE", "PUBLIC_DEMO")
    if mode not in {"PUBLIC_DEMO", "TEAM_TEST", "COMPANY"}:
        raise unavailable()
    origin = os.environ.get("FS_PUBLIC_ORIGIN", "")
    box = None
    keys = os.environ.get("FS_SECURITY_KEYS")
    if keys:
        try:
            mapping = json.loads(keys)
            if not isinstance(mapping, dict) or not all(
                isinstance(v, str) for v in mapping.values()
            ):
                raise ValueError("invalid keys")
            box = SecretBox(
                os.environ.get("FS_SECURITY_KEY_ID", ""),
                {k: v.encode() for k, v in mapping.items()},
            )
        except TypeError, ValueError:
            raise unavailable() from None
    if mode == "COMPANY":
        parsed = urlsplit(origin)
        if (
            box is None
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or os.environ.get("COOKIE_SECURE", "true").lower() in {"false", "0", "no"}
        ):
            raise unavailable()
    return SecuritySettings(mode, origin.rstrip("/"), box)
