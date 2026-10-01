"""FS-040 런처 평가 AC-240~246."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.core.service import create_member_account
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, text


def _post(client, csrf: str, body: dict, key: str | None = None):
    return client.post(
        "/api/v1/core/reviews",
        json=body,
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key or str(uuid4())},
    )


def _new_guest(client, nickname: str = "다른 게스트"):
    # 쿠키를 비워야 새 게스트 공간이 생긴다(나갔다가 다시 들어온 방문자).
    client.cookies.clear()
    response = client.post(
        "/api/v1/core/guest-sessions",
        json={"nickname": nickname},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["csrfToken"]


@pytest.fixture
def reviews(guest_space):
    client, session, engine = guest_space
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM core.app_review"))
    yield client, session["csrfToken"], engine
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM core.app_review"))


def _count(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT count(*) FROM core.app_review")
        ).scalar_one()


@pytest.mark.parametrize(
    "body",
    [
        {"moduleKey": "mes", "rating": 0, "comment": "좋아요", "nickname": "별칭"},
        {"moduleKey": "mes", "rating": 6, "comment": "좋아요", "nickname": "별칭"},
        {"moduleKey": "mes", "rating": 5, "comment": " 좋 ", "nickname": "별칭"},
        {"moduleKey": "mes", "rating": 5, "comment": "가" * 101, "nickname": "별칭"},
        {"moduleKey": "core", "rating": 5, "comment": "좋아요", "nickname": "별칭"},
        {"moduleKey": "mes", "rating": 5, "comment": "좋아요", "nickname": " 별 "},
    ],
)
def test_invalid_input_is_400(reviews, body):
    """AC-240"""
    client, csrf, engine = reviews
    response = _post(client, csrf, body)
    assert response.status_code == 400, response.text
    assert _count(engine) == 0


def test_guest_review_flow(reviews):
    """AC-241·242·243·245·246"""
    client, csrf, engine = reviews
    body = {
        "moduleKey": "mes",
        "rating": 4,
        "comment": " 작업지시가 편해요 ",
        "nickname": " 현장1 ",
    }
    first = _post(client, csrf, body, key="same-key")
    assert first.status_code == 201, first.text
    assert (first.json()["data"]["nickname"], first.json()["data"]["comment"]) == (
        "현장1",
        "작업지시가 편해요",
    )
    # AC-245 같은 키 재전송 → 같은 결과
    again = _post(client, csrf, body, key="same-key")
    assert again.status_code == 201 and again.json()["data"] == first.json()["data"]
    # AC-242 같은 공간에서 별칭을 바꿔도 다시 평가할 수 없다
    dup = _post(client, csrf, {**body, "nickname": "현장2"})
    assert dup.json()["error"]["code"] == "ALREADY_REVIEWED"
    summary = client.get("/api/v1/core/reviews/summary").json()["data"]
    assert summary == [
        {"moduleKey": "mes", "average": 4.0, "count": 1, "reviewed": True}
    ]
    # AC-243 새 게스트: 같은 별칭은 거부, 다른 별칭은 허용
    csrf2 = _new_guest(client)
    taken = _post(client, csrf2, {**body, "rating": 2})
    assert (taken.status_code, taken.json()["error"]["code"]) == (409, "NICKNAME_TAKEN")
    ok = _post(client, csrf2, {**body, "rating": 2, "nickname": "현장2"})
    assert ok.status_code == 201, ok.text
    summary = client.get("/api/v1/core/reviews/summary").json()["data"]
    assert summary == [
        {"moduleKey": "mes", "average": 3.0, "count": 2, "reviewed": True}
    ]
    recent = client.get("/api/v1/core/reviews", params={"moduleKey": "mes"}).json()[
        "data"
    ]
    assert [r["nickname"] for r in recent] == ["현장2", "현장1"]
    # 다른 솔루션은 따로 1회
    assert (
        _post(
            client, csrf2, {**body, "moduleKey": "wms", "nickname": "현장2"}
        ).status_code
        == 201
    )
    # AC-246 게스트 공간이 지워져도 평가는 남는다(공간 FK 없음)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM core.app_review r JOIN core.workspace w ON w.guest_actor_key=r.guest_actor_key"
                )
            ).scalar_one()
            == 3
        )


def test_review_requires_csrf(reviews):
    client, _, engine = reviews
    response = _post(
        client,
        "wrong",
        {"moduleKey": "mes", "rating": 5, "comment": "좋아요", "nickname": "별칭"},
    )
    assert response.status_code in (401, 403)
    assert _count(engine) == 0


PASSWORD = "synthetic-member-pass-01"


def test_member_reviews_once_with_display_name(clean_database, monkeypatch):
    """AC-244"""
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv(
        "SESSION_SECRET", "review-synthetic-test-secret-at-least-32-characters"
    )
    reset_engine()
    with engine.begin() as connection:
        create_template(connection, date(2026, 9, 24))
        create_member_account(
            connection, "reviewer", "평가하는 회원", PASSWORD, date(2026, 9, 24)
        )
    try:
        with TestClient(create_app(), base_url="https://testserver") as client:
            login = client.post(
                "/api/v1/core/sessions",
                json={"loginId": "reviewer", "password": PASSWORD},
                headers={"Idempotency-Key": "login"},
            )
            csrf = login.json()["data"]["csrfToken"]
            body = {
                "moduleKey": "erp",
                "rating": 5,
                "comment": "수주 흐름이 보여요",
                "nickname": "무시됨",
            }
            first = _post(client, csrf, body)
            assert first.status_code == 201, first.text
            assert first.json()["data"]["nickname"] == "평가하는 회원"
            second = _post(client, csrf, body)
            assert (second.status_code, second.json()["error"]["code"]) == (
                409,
                "ALREADY_REVIEWED",
            )
            assert (
                client.get("/api/v1/core/reviews/summary").json()["data"][0]["reviewed"]
                is True
            )
    finally:
        reset_engine()
