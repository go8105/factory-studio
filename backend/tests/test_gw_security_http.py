"""Actual cookie/challenge/CSRF protocol; synthetic account and isolated DB only."""

# ruff: noqa: F401, F811
from uuid import uuid4

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_gw_security_transactions import identity

from fs.common.db import reset_engine
from fs.main import create_app


def test_login_enroll_otp_recovery_http(identity, monkeypatch):
    engine, context, password, login = identity
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("COOKIE_SECURE", "false")
    reset_engine()
    try:
        with TestClient(create_app()) as client:

            def login_request():
                return client.post(
                    "/api/v1/core/sessions",
                    json={"loginId": login, "password": password},
                    headers={"Idempotency-Key": str(uuid4())},
                )

            initial = login_request()
            assert initial.status_code == 201
            csrf = initial.json()["data"]["csrfToken"]
            start = client.post(
                "/api/v1/core/security/enrollment/start",
                json={"password": password},
                headers={"X-CSRF-Token": csrf},
            )
            assert start.status_code == 200
            data = start.json()["data"]
            confirm = client.post(
                "/api/v1/core/security/enrollment/confirm",
                json={
                    "factorId": data["factorId"],
                    "code": pyotp.TOTP(data["setupKey"]).now(),
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert confirm.status_code == 200
            codes = confirm.json()["data"]["recoveryCodes"]
            assert client.get("/api/v1/core/sessions/current").status_code == 401
            challenge = login_request()
            assert challenge.status_code == 202
            assert (
                "fs_auth_challenge" in client.cookies
                and "fs_session" not in client.cookies
            )
            challenge_csrf = challenge.json()["data"]["challengeCsrfToken"]
            assert (
                client.post(
                    "/api/v1/core/security/login/verify", json={"code": codes[0]}
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/core/security/login/verify",
                    json={"code": codes[0]},
                    headers={
                        "X-CSRF-Token": challenge_csrf,
                        "Origin": "https://attacker.invalid",
                    },
                ).status_code
                == 403
            )
            recovered = client.post(
                "/api/v1/core/security/login/verify",
                json={"code": codes[0]},
                headers={"X-CSRF-Token": challenge_csrf},
            )
            assert (
                recovered.status_code == 201
                and recovered.json()["data"]["recoveryOnly"] is True
            )
            # Cookie survives denial so the dedicated enrollment can finish.
            denied = client.get("/api/v1/core/sessions/current")
            assert (
                denied.status_code == 403
                and denied.json()["error"]["code"] == "RECOVERY_ONLY"
            )
            assert client.get("/api/v1/core/workspace").status_code == 403
            status = client.get("/api/v1/core/security/recovery/status")
            assert status.status_code == 200
            csrf = status.json()["data"]["csrfToken"]
            pending = client.post(
                "/api/v1/core/security/recovery/start", headers={"X-CSRF-Token": csrf}
            )
            assert pending.status_code == 200
            next_data = pending.json()["data"]
            complete = client.post(
                "/api/v1/core/security/recovery/complete",
                json={
                    "factorId": next_data["factorId"],
                    "code": pyotp.TOTP(next_data["setupKey"]).now(),
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert complete.status_code == 200
            challenge = login_request()
            assert challenge.status_code == 202
            with engine.begin() as c:
                c.execute(
                    text(
                        "UPDATE core.mfa_factor SET last_used_step=NULL WHERE user_id=:u AND state='ACTIVE'"
                    ),
                    {"u": context.user_id},
                )
            verified = client.post(
                "/api/v1/core/security/login/verify",
                json={"code": pyotp.TOTP(next_data["setupKey"]).now()},
                headers={
                    "X-CSRF-Token": challenge.json()["data"]["challengeCsrfToken"]
                },
            )
            assert (
                verified.status_code == 201
                and verified.json()["data"]["actorKind"] == "MEMBER"
            )
            assert client.get("/api/v1/core/sessions/current").status_code == 200
            assert (
                client.get("/api/v1/core/security/me").json()["data"]["mfaRegistered"]
                is True
            )
            assert "no-store" in verified.headers["Cache-Control"]
    finally:
        reset_engine()
