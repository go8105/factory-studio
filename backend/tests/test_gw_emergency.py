"""Synthetic company emergency recovery: two parties, no business session bypass."""

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.core.security import emergency as credentials
from fs.gw.emergency import approve
from fs.hr.work_setup import create_company
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import text


@pytest.fixture
def emergency_env(clean_database, monkeypatch):
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("SESSION_SECRET", "synthetic-emergency-test-session-secret-32")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("FS_SECURITY_MODE", "TEAM_TEST")
    monkeypatch.setenv("FS_SECURITY_KEY_ID", "test")
    monkeypatch.setenv(
        "FS_SECURITY_KEYS", json.dumps({"test": Fernet.generate_key().decode()})
    )
    reset_engine()
    password = uuid4().hex
    with engine.begin() as c:
        create_template(c, date(2026, 10, 18))
        co = create_company(
            c,
            {
                "companyName": "합성 긴급 복구 회사",
                "loginId": "synthetic-emergency-owner",
                "name": "합성 책임자",
                "password": password,
                "employeeCode": "SYN-EMERGENCY",
                "workStart": "09:00",
                "dailyMinutes": 480,
                "breakMinutes": 60,
                "annualDays": 15,
            },
        )
    client = TestClient(create_app())

    def login():
        return client.post(
            "/api/v1/core/sessions",
            json={"loginId": "synthetic-emergency-owner", "password": password},
            headers={"Idempotency-Key": str(uuid4())},
        )

    initial = login()
    assert initial.status_code == 201
    csrf = initial.json()["data"]["csrfToken"]
    setup = client.post(
        "/api/v1/gw/company-setup",
        params={"companyId": co["companyId"]},
        json={"employeeCode": "SYN-EMERGENCY", "reason": "합성 관리자 준비"},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
    )
    assert setup.status_code == 200, setup.text
    start = client.post(
        "/api/v1/core/security/enrollment/start",
        json={"password": password},
        headers={"X-CSRF-Token": csrf},
    ).json()["data"]
    enrolled = client.post(
        "/api/v1/core/security/enrollment/confirm",
        json={
            "factorId": start["factorId"],
            "code": pyotp.TOTP(start["setupKey"]).now(),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert enrolled.status_code == 200
    challenge = login()
    assert challenge.status_code == 202
    with engine.connect() as c:
        db_now = c.execute(text("SELECT clock_timestamp()")).scalar_one()
    next_code = pyotp.TOTP(start["setupKey"]).at(db_now + timedelta(seconds=30))
    full = client.post(
        "/api/v1/core/security/login/verify",
        json={"code": next_code},
        headers={"X-CSRF-Token": challenge.json()["data"]["challengeCsrfToken"]},
    )
    assert full.status_code == 201, full.text
    client.csrf = full.json()["data"]["csrfToken"]
    yield engine, co, client, login
    client.close()
    reset_engine()


def issue(env, *, key=None):
    _engine, co, client, _login = env
    return client.post(
        "/api/v1/gw/emergency-kit",
        params={"companyId": co["companyId"]},
        json={"reason": "별도 보관용 합성 긴급 문서"},
        headers={"X-CSRF-Token": client.csrf, "Idempotency-Key": key or str(uuid4())},
    )


def test_kit_once_response_replaces_previous_and_no_credentials_in_audit(emergency_env):
    engine, co, client, _login = emergency_env
    key = str(uuid4())
    first = issue(emergency_env, key=key)
    assert first.status_code == 200, first.text
    kit = first.json()["data"]["kit"]
    second = issue(emergency_env)
    assert second.status_code == 200
    # Retry an older key after another issuance must not rotate again.
    assert issue(emergency_env, key=key).status_code == 409
    with engine.begin() as c:
        _, error = approve(
            c, credentials.EmergencyKit.model_validate(kit), 501, "합성 운영자 승인"
        )
        assert error is not None
        rows = (
            c.execute(
                text(
                    "SELECT protected_payload FROM core.authentication_challenge WHERE purpose='RECOVERY'"
                )
            )
            .scalars()
            .all()
        )
        audit = (
            c.execute(
                text(
                    "SELECT summary::text FROM core.audit_event WHERE action LIKE 'security.emergency%'"
                )
            )
            .scalars()
            .all()
        )
        assert not any(kit["kitSecret"] in value for value in rows + audit)
    status = client.get(
        "/api/v1/gw/operations", params={"companyId": co["companyId"]}
    ).json()["data"]
    assert status["emergencyKit"]["prepared"] is True


def test_operator_approval_race_and_http_recovery_never_issues_business_session(
    emergency_env,
):
    engine, _co, client, login = emergency_env
    kit = credentials.EmergencyKit.model_validate(
        issue(emergency_env).json()["data"]["kit"]
    )

    def authorize(_):
        with engine.begin() as c:
            return approve(c, kit, 501, "합성 운영자 본인 확인")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(authorize, range(2)))
    assert sum(error is None for _, error in results) == 1
    grant = next(value for value, error in results if error is None)
    # Approval itself leaves the user's existing real MFA session intact.
    assert client.get("/api/v1/core/sessions/current").status_code == 200
    client.cookies.clear()
    challenge = login()
    assert challenge.status_code == 202
    headers = {"X-CSRF-Token": challenge.json()["data"]["challengeCsrfToken"]}
    path = "/api/v1/core/security/login/emergency"
    assert (
        client.post(path, json={"grantToken": grant["grantToken"]}).status_code == 403
    )
    assert (
        client.post(
            path,
            json={"grantToken": grant["grantToken"]},
            headers=headers | {"Origin": "https://attacker.invalid"},
        ).status_code
        == 403
    )
    recovered = client.post(
        path, json={"grantToken": grant["grantToken"]}, headers=headers
    )
    assert (
        recovered.status_code == 201
        and recovered.json()["data"]["recoveryOnly"] is True
    )
    assert client.get("/api/v1/core/workspace").status_code == 403
    csrf = recovered.json()["data"]["csrfToken"]
    start = client.post(
        "/api/v1/core/security/recovery/start", headers={"X-CSRF-Token": csrf}
    ).json()["data"]
    finish = client.post(
        "/api/v1/core/security/recovery/complete",
        json={
            "factorId": start["factorId"],
            "code": pyotp.TOTP(start["setupKey"]).now(),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert finish.status_code == 200
    challenge = login()
    assert challenge.status_code == 202
    replay = client.post(
        path,
        json={"grantToken": grant["grantToken"]},
        headers={"X-CSRF-Token": challenge.json()["data"]["challengeCsrfToken"]},
    )
    assert replay.status_code == 401


def test_current_role_and_expired_approval_are_rechecked(emergency_env):
    engine, co, client, login = emergency_env
    kit = credentials.EmergencyKit.model_validate(
        issue(emergency_env).json()["data"]["kit"]
    )
    with engine.begin() as c:
        grant, error = approve(c, kit, 501, "합성 운영자 확인")
        assert error is None
        c.execute(
            text(
                "UPDATE gw.role_grant SET is_active=false WHERE workspace_id=:w AND role_key='SECURITY_ADMIN'"
            ),
            {"w": co["companyId"]},
        )
    assert issue(emergency_env).status_code == 403
    client.cookies.clear()
    challenge = login()
    response = client.post(
        "/api/v1/core/security/login/emergency",
        json={"grantToken": grant["grantToken"]},
        headers={"X-CSRF-Token": challenge.json()["data"]["challengeCsrfToken"]},
    )
    assert response.status_code == 403
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.role_grant SET is_active=true WHERE workspace_id=:w AND role_key='SECURITY_ADMIN'"
            ),
            {"w": co["companyId"]},
        )
        c.execute(
            text(
                "UPDATE core.authentication_challenge SET created_at=clock_timestamp()-interval '20 minutes',expires_at=clock_timestamp()-interval '1 minute' WHERE provider_key LIKE 'gw-grant:%'"
            )
        )
    response = client.post(
        "/api/v1/core/security/login/emergency",
        json={"grantToken": grant["grantToken"]},
        headers={"X-CSRF-Token": challenge.json()["data"]["challengeCsrfToken"]},
    )
    assert response.status_code == 401


def test_wrong_kit_attempts_persist_and_operator_file_is_private(
    emergency_env, tmp_path
):
    engine, _co, _client, _login = emergency_env
    kit = issue(emergency_env).json()["data"]["kit"]
    bad = credentials.EmergencyKit.model_validate(kit | {"kitSecret": "x" * 43})
    for _ in range(5):
        with engine.begin() as c:
            _, error = approve(c, bad, 501, "합성 실패 제한 검증")
        assert error is not None
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT state,attempt_count FROM core.authentication_challenge WHERE id=:id"
            ),
            {"id": int(kit["kitId"])},
        ).one()
        assert tuple(row) == ("LOCKED", 5)
    kit = issue(emergency_env).json()["data"]["kit"]
    kitfile = tmp_path / "synthetic-kit.json"
    kitfile.write_text(json.dumps(kit))
    kitfile.chmod(0o600)
    output = tmp_path / "synthetic-grant.json"
    result = subprocess.run(
        [
            str(Path("backend/.venv/bin/python").absolute()),
            "tools/gw_emergency_recovery.py",
            "--kit-file",
            str(kitfile),
            "--output",
            str(output),
            "--company-id",
            kit["companyId"],
            "--user-id",
            kit["userId"],
            "--reason",
            "합성 운영자 승인",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    grant = json.loads(output.read_text())
    assert len(grant["grantToken"]) == 43
    assert output.stat().st_mode & 0o777 == 0o600
    assert (
        kit["kitSecret"] not in result.stdout + result.stderr
        and grant["grantToken"] not in result.stdout + result.stderr
    )
    # Existing output is not overwritten, even with another valid kit.
    other = issue(emergency_env).json()["data"]["kit"]
    kitfile.write_text(json.dumps(other))
    again = subprocess.run(
        [
            str(Path("backend/.venv/bin/python").absolute()),
            "tools/gw_emergency_recovery.py",
            "--kit-file",
            str(kitfile),
            "--output",
            str(output),
            "--company-id",
            other["companyId"],
            "--user-id",
            other["userId"],
            "--reason",
            "합성 중복 경로",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert again.returncode != 0 and json.loads(output.read_text()) == grant


def test_company_management_requires_recent_auth_before_replaying_receipt(
    emergency_env, monkeypatch
):
    engine, co, client, _login = emergency_env
    with engine.connect() as c:
        person = (
            c.execute(
                text(
                    "SELECT id,version FROM gw.person WHERE workspace_id=:w AND hr_employee_code='SYN-EMERGENCY'"
                ),
                {"w": co["companyId"]},
            )
            .mappings()
            .one()
        )
    path = f"/api/v1/gw/people/{person['id']}/roles"
    body = {
        "expectedVersion": person["version"],
        "roles": ["SECURITY_ADMIN", "ORG_ADMIN"],
        "reason": "합성 최근 인증 역할 검증",
    }
    key = str(uuid4())
    headers = {"X-CSRF-Token": client.csrf, "Idempotency-Key": key}
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("FS_PUBLIC_ORIGIN", "https://testserver")
    monkeypatch.setenv("FS_SECURITY_MODE", "COMPANY")
    # Existing synthetic cookie; this test concentrates on current authorization.
    with TestClient(create_app(), base_url="https://testserver") as secure:
        secure.cookies.update(client.cookies)
        first = secure.patch(
            path, params={"companyId": co["companyId"]}, json=body, headers=headers
        )
        assert first.status_code == 200, first.text
        with engine.begin() as c:
            c.execute(
                text(
                    "UPDATE core.auth_session SET verified_at=clock_timestamp()-interval '6 minutes' WHERE revoked_at IS NULL"
                )
            )
        denied = secure.patch(
            path, params={"companyId": co["companyId"]}, json=body, headers=headers
        )
        assert (
            denied.status_code == 403
            and denied.json()["error"]["code"] == "STEP_UP_REQUIRED"
        )
        # This is the same completed command/key; freshness must precede receipt replay.
        with engine.begin() as c:
            c.execute(
                text(
                    "UPDATE core.auth_session SET verified_at=clock_timestamp() WHERE revoked_at IS NULL"
                )
            )
        replay = secure.patch(
            path, params={"companyId": co["companyId"]}, json=body, headers=headers
        )
        assert replay.status_code == 200 and replay.json() == first.json()


def test_new_kit_invalidates_pending_operator_approval(emergency_env):
    engine, _co, client, login = emergency_env
    kit = credentials.EmergencyKit.model_validate(
        issue(emergency_env).json()["data"]["kit"]
    )
    with engine.begin() as c:
        grant, error = approve(c, kit, 501, "합성 승인 후 교체")
    assert error is None
    assert issue(emergency_env).status_code == 200
    client.cookies.clear()
    challenge = login()
    r = client.post(
        "/api/v1/core/security/login/emergency",
        json={"grantToken": grant["grantToken"]},
        headers={"X-CSRF-Token": challenge.json()["data"]["challengeCsrfToken"]},
    )
    assert r.status_code == 401


def test_cli_keeps_written_grant_when_commit_result_is_uncertain(
    emergency_env, tmp_path, monkeypatch
):
    import importlib.util
    from contextlib import contextmanager

    from sqlalchemy.exc import OperationalError

    kit = issue(emergency_env).json()["data"]["kit"]
    kit_path = tmp_path / "kit.json"
    kit_path.write_text(json.dumps(kit))
    kit_path.chmod(0o600)
    output = tmp_path / "approval.json"
    spec = importlib.util.spec_from_file_location(
        "emergency_cli", Path(__file__).parents[2] / "tools/gw_emergency_recovery.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    class UncertainEngine:
        @contextmanager
        def begin(self):
            yield object()
            raise OperationalError("commit", {}, Exception("synthetic disconnect"))

        def dispose(self):
            pass

    monkeypatch.setattr(cli, "create_engine", lambda _: UncertainEngine())
    grant = "a" * 43
    monkeypatch.setattr(
        cli,
        "approve",
        lambda *args: ({"grantToken": grant, "expiresAt": "synthetic"}, None),
    )
    with pytest.raises(OperationalError):
        cli.run(
            kit_path,
            output,
            "合成 commit不明",
            company_id=kit["companyId"],
            user_id=kit["userId"],
        )
    assert json.loads(output.read_text())["grantToken"] == grant
    assert output.stat().st_mode & 0o777 == 0o600
