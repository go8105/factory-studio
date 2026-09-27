"""DB-free API tests, including the locally built real native executable."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fs.common.auth import AuthContext, resolve_auth
from fs.common.security import guest_csrf_token
from fs.factory import native
from fs.main import create_app

SECRET = "native-test-secret-32-characters-long"
BODY = {
    "requestId": "test:1",
    "request": {
        "version": 1,
        "sample": "foreign",
        "recipe": {"threshold": 90, "minArea": 20, "roi": "full"},
    },
}
BINARY = (
    Path(__file__).resolve().parents[2] / "work/inspection-core/bin/inspection_core"
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused/unused_test")
    monkeypatch.setenv("SESSION_SECRET", SECRET)
    monkeypatch.delenv("VISION_CORE_EXECUTABLE", raising=False)
    app = create_app()
    app.dependency_overrides[resolve_auth] = lambda: AuthContext(
        "GUEST", "demo", 10, 20, None, frozenset({"GUEST"}), "g_native"
    )
    with TestClient(app) as client:
        yield client


def headers():
    return {"X-CSRF-Token": guest_csrf_token(SECRET, "g_native")}


def post(client, body=BODY):
    return client.post("/api/v1/factory/vision/inspect", json=body, headers=headers())


def test_unconfigured_and_csrf(client):
    assert post(client).status_code == 503
    assert client.post("/api/v1/factory/vision/inspect", json=BODY).status_code == 403


def test_auth_required(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused/unused_test")
    monkeypatch.setenv("SESSION_SECRET", SECRET)
    with TestClient(create_app()) as client:
        assert (
            client.post("/api/v1/factory/vision/inspect", json=BODY).status_code == 401
        )


@pytest.mark.parametrize(
    "patch", [{"minArea": 0}, {"threshold": True}, {"threshold": 256}, {"roi": "other"}]
)
def test_request_validation(client, patch):
    body = {
        **BODY,
        "request": {
            **BODY["request"],
            "recipe": {**BODY["request"]["recipe"], **patch},
        },
    }
    assert post(client, body).status_code == 400


def test_real_binary(client, monkeypatch):
    if not BINARY.exists():
        pytest.skip("Build native core first")
    monkeypatch.setenv("VISION_CORE_EXECUTABLE", str(BINARY))
    response = post(client)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["requestId"] == BODY["requestId"]
    assert data["result"]["source"] == "synthetic-opencv-cpp-v1"
    assert [r["area"] for r in data["result"]["regions"]] == [80, 36]
    assert data["inspectionMs"] >= 0
    assert response.headers["cache-control"] == "no-store"


def fake_binary(tmp_path, monkeypatch, code):
    p = tmp_path / "engine"
    p.write_text("#!/usr/bin/env python3\n" + code)
    p.chmod(0o755)
    monkeypatch.setenv("VISION_CORE_EXECUTABLE", str(p))


@pytest.mark.parametrize(
    "code",
    ["print('not json')", "print('{}')", "raise SystemExit(1)", "print('x'*1100000)"],
)
def test_bad_native_output(client, monkeypatch, tmp_path, code):
    fake_binary(tmp_path, monkeypatch, code)
    assert post(client).status_code == 502


def test_timeout_and_slot_recovery(client, monkeypatch, tmp_path):
    fake_binary(tmp_path, monkeypatch, "import time;time.sleep(5)")
    monkeypatch.setattr(native, "TIMEOUT", 0.05)
    assert post(client).status_code == 504
    assert native._slots.acquire(blocking=False)
    native._slots.release()


def test_busy(client, monkeypatch, tmp_path):
    fake_binary(tmp_path, monkeypatch, "print('{}')")
    for _ in range(4):
        assert native._slots.acquire(blocking=False)
    try:
        assert post(client).status_code == 429
    finally:
        for _ in range(4):
            native._slots.release()


def test_cancel_releases_slot(monkeypatch, tmp_path):
    fake_binary(tmp_path, monkeypatch, "import time;time.sleep(5)")

    async def run():
        task = asyncio.create_task(
            native.inspect_native(native.NativeRequest.model_validate(BODY))
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert native._slots.acquire(blocking=False)
    native._slots.release()
