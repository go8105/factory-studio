from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    session_secret: str
    session_cookie: str = "fs_session"
    session_idle_minutes: int = 30
    guest_limit: int = 20
    cookie_secure: bool = True


def cookie_secure() -> bool:
    # COOKIE_SECURE=false 이면 로컬 HTTP 환경에서도 쿠키가 저장된다 (기본값: true).
    # SESSION_SECRET 없이도 읽을 수 있어야 오류 핸들러가 500으로 바뀌지 않는다.
    return os.environ.get("COOKIE_SECURE", "true").lower() not in {"false", "0", "no"}


def get_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    session_secret = os.environ.get("SESSION_SECRET")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not session_secret or len(session_secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
    return Settings(
        database_url=database_url,
        session_secret=session_secret,
        guest_limit=int(os.environ.get("GUEST_LIMIT", "20")),
        cookie_secure=cookie_secure(),
    )
