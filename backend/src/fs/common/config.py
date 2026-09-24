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


def get_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    session_secret = os.environ.get("SESSION_SECRET")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not session_secret or len(session_secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
    return Settings(database_url=database_url, session_secret=session_secret)
