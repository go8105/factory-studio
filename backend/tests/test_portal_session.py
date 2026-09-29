"""FS-017 browser session recovery, independent of antigravity test files."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, text


@pytest.fixture
def portal_client(clean_database: Engine, monkeypatch: pytest.MonkeyPatch):
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv(
        "SESSION_SECRET", "fs017-synthetic-test-secret-at-least-32-characters"
    )
    reset_engine()
    with engine.begin() as connection:
        create_template(connection, date(2026, 9, 24))
    with TestClient(create_app(), base_url="https://testserver") as client:
        created = client.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "테스트 게스트"},
            headers={"Idempotency-Key": "portal-guest"},
        )
        assert created.status_code == 201
        yield client, created.json()["data"], engine
    reset_engine()


def test_current_session_restores_guest_csrf(portal_client):
    client, created, _ = portal_client
    current = client.get("/api/v1/core/sessions/current")
    assert current.json()["data"]["csrfToken"] == created["csrfToken"]


def test_restored_csrf_allows_module_update(portal_client):
    client, _, _ = portal_client
    csrf = client.get("/api/v1/core/sessions/current").json()["data"]["csrfToken"]
    response = client.patch(
        "/api/v1/core/workspace/modules/mes",
        json={"enabled": False},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "reload-module"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["enabled"] is False


def test_expired_guest_response_removes_cookie(portal_client):
    client, created, engine = portal_client
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace SET expires_at=now()-interval '1 minute' WHERE id=:id"
            ),
            {"id": created["workspaceId"]},
        )
    response = client.get("/api/v1/core/sessions/current")
    assert response.status_code == 410
    assert "fs_session" not in client.cookies


def test_expired_guest_can_create_new_space(portal_client):
    client, created, engine = portal_client
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace SET expires_at=now()-interval '1 minute' WHERE id=:id"
            ),
            {"id": created["workspaceId"]},
        )
    client.get("/api/v1/core/sessions/current")
    response = client.post(
        "/api/v1/core/guest-sessions",
        json={"nickname": "테스트 게스트"},
        headers={"Idempotency-Key": "new-guest"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["workspaceId"] != created["workspaceId"]
