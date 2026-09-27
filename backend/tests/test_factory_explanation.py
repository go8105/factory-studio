"""DB-free API/adapter tests; provider and authentication are explicitly stubbed."""

import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient
from fs.common.auth import AuthContext, resolve_auth
from fs.common.security import guest_csrf_token
from fs.factory import explanation as service
from fs.main import create_app


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused/unused_test")
    monkeypatch.setenv("SESSION_SECRET", "factory-test-secret-32-characters-long")
    service._cache.clear()
    monkeypatch.setattr(service, "_retry_at", 0)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[resolve_auth] = lambda: AuthContext(
        "GUEST", "demo", 10, 20, None, frozenset({"GUEST"}), "g_factory"
    )
    with TestClient(app) as client:
        yield client


def headers():
    return {
        "X-CSRF-Token": guest_csrf_token(
            "factory-test-secret-32-characters-long", "g_factory"
        )
    }


@pytest.mark.parametrize("scenario", list(service.SCENARIOS))
def test_unconfigured_returns_labelled_demo_and_evidence(client, scenario, monkeypatch):
    monkeypatch.setattr(
        service, "urlopen", lambda *a, **k: pytest.fail("No provider call without key")
    )
    response = client.post(
        "/api/v1/factory/vision/explanation",
        json={"scenario": scenario},
        headers=headers(),
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["mode"] == "demo" and result["model"] is None
    assert result["reason"] == "not_configured"
    assert result["evidence"] == service.evidence(scenario)
    assert response.headers["cache-control"] == "no-store"


def test_server_calculates_percentage_point_difference():
    assert service.evidence("reject-rise")[2] == "불합격률 변화: +18%p"
    assert service.evidence("stopped")[2] == "불합격률 변화: +0%p"


def test_authentication_required():
    with TestClient(create_app()) as client:
        assert (
            client.post(
                "/api/v1/factory/vision/explanation", json={"scenario": "normal"}
            ).status_code
            == 401
        )


def test_csrf_and_closed_request_schema(client):
    assert (
        client.post(
            "/api/v1/factory/vision/explanation", json={"scenario": "normal"}
        ).status_code
        == 403
    )
    for body in (
        {"scenario": "other"},
        {"scenario": "normal", "prompt": "arbitrary"},
        {"scenario": "normal", "workspaceId": 999},
    ):
        assert (
            client.post(
                "/api/v1/factory/vision/explanation", json=body, headers=headers()
            ).status_code
            == 400
        )


def provider_response(narrative=None, status="completed"):
    return {
        "status": status,
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            narrative
                            or {
                                "summary": "상태 설명",
                                "hypotheses": ["원인 미확정"],
                                "checks": ["기록 확인"],
                            }
                        ),
                    }
                ],
            },
        ],
    }


def test_real_adapter_request_and_finite_cache(monkeypatch, client):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")
    calls = []

    def fake_open(request, timeout):
        calls.append(json.loads(request.data))
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert timeout == 25
        return io.BytesIO(json.dumps(provider_response()).encode())

    monkeypatch.setattr(service, "urlopen", fake_open)
    for _ in range(2):
        result = client.post(
            "/api/v1/factory/vision/explanation",
            json={"scenario": "normal"},
            headers=headers(),
        ).json()["data"]
        assert result["mode"] == "ai" and result["model"] == "gpt-6-astra"
        assert result["narrative"]["summary"] == "상태 설명"
    assert len(calls) == 1
    assert calls[0]["store"] is False
    assert calls[0]["text"]["format"]["strict"] is True
    assert "workspace" not in calls[0]["input"] and "g_factory" not in json.dumps(
        calls[0]
    )


@pytest.mark.parametrize(
    "raw",
    [
        provider_response(status="incomplete"),
        {"status": "completed", "output": []},
        provider_response({"summary": "oops"}),
        provider_response({"summary": "x" * 501, "hypotheses": ["x"], "checks": ["x"]}),
    ],
)
def test_invalid_model_output_becomes_demo(monkeypatch, raw):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setattr(
        service, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(raw).encode())
    )
    assert service.explain("normal")["reason"] == "unavailable"


def test_provider_failure_does_not_expose_secret_and_cools_down(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-secret")
    calls = []

    def fail(*a, **k):
        calls.append(1)
        raise URLError("test-only-secret provider internal detail")

    monkeypatch.setattr(service, "urlopen", fail)
    result = service.explain("normal")
    assert result["mode"] == "demo"
    assert "secret" not in json.dumps(result)
    assert service.explain("reject-rise")["reason"] == "busy"
    assert len(calls) == 1


def test_parallel_clicks_do_not_duplicate_paid_request(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    started, release = Event(), Event()

    def generate(scenario, key):
        started.set()
        assert release.wait(3)
        return {
            **service.demo_result(scenario, "test"),
            "mode": "ai",
            "model": service.MODEL,
        }

    monkeypatch.setattr(service, "generate", generate)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(service.explain, "normal")
        assert started.wait(3)
        try:
            assert service.explain("normal")["reason"] == "busy"
        finally:
            release.set()
        assert future.result()["mode"] == "ai"
