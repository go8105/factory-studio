"""운영자 회원 계정 생성(tools/create_member.py)과 회원 로그인 오류 코드."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.core.service import create_member_account
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine

PASSWORD = "synthetic-member-pass-01"


@pytest.fixture
def member_env(clean_database: Engine, monkeypatch: pytest.MonkeyPatch):
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv(
        "SESSION_SECRET", "member-synthetic-test-secret-at-least-32-characters"
    )
    reset_engine()
    with engine.begin() as connection:
        create_template(connection, date(2026, 9, 24))
        result = create_member_account(
            connection, " Ops ", "운영자", PASSWORD, date(2026, 9, 24), admin=True
        )
    with TestClient(create_app(), base_url="https://testserver") as client:
        yield client, result, engine
    reset_engine()


def _login(client, login_id: str, password: str, key: str):
    return client.post(
        "/api/v1/core/sessions",
        json={"loginId": login_id, "password": password},
        headers={"Idempotency-Key": key},
    )


def test_created_member_logs_in_with_copied_data_and_admin_role(member_env):
    client, result, _ = member_env
    assert (result["loginId"], result["admin"]) == ("ops", True)
    assert result["copiedRows"] > 7000  # 템플릿 업무 데이터가 회원 공간에 복사됨
    response = _login(client, "ops", PASSWORD, "member-ok")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert (data["actorKind"], data["roles"]) == ("MEMBER", ["ADMIN"])
    assert client.get("/api/v1/erp/dashboard").status_code == 200


def test_wrong_password_is_invalid_credentials_not_session_expired(member_env):
    client, _, _ = member_env
    for login_id, password in (("ops", "wrong-password-00"), ("nobody", PASSWORD)):
        response = _login(client, login_id, password, f"bad-{login_id}")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_duplicate_or_short_password_is_refused(member_env):
    _, _, engine = member_env
    with engine.begin() as connection:
        with pytest.raises(ValueError, match="이미 있는"):
            create_member_account(connection, "OPS", "x", PASSWORD, date(2026, 9, 24))
        with pytest.raises(ValueError, match="10자"):
            create_member_account(connection, "new", "x", "short", date(2026, 9, 24))
