from __future__ import annotations

import logging
import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text

from fs.common.db import reset_engine
from fs.common.security import hash_password, token_hash
from fs.core.service import cleanup_expired_guests
from fs.main import create_app
from seed.generate import create_template


def _business_count(engine: Engine, workspace_id: int, generation_id: int) -> int:
    total = 0
    with engine.connect() as connection:
        for schema in ("mes", "erp", "fems"):
            for table in inspect(connection).get_table_names(schema=schema):
                total += connection.execute(
                    text(
                        f'SELECT count(*) FROM "{schema}"."{table}" '
                        "WHERE workspace_id=:w AND generation_id=:g"
                    ),
                    {"w": workspace_id, "g": generation_id},
                ).scalar_one()
        total += connection.execute(
            text("SELECT count(*) FROM core.workspace_module WHERE workspace_id=:w"),
            {"w": workspace_id},
        ).scalar_one()
    return total


def _create_member(engine: Engine) -> tuple[int, int]:
    with engine.begin() as connection:
        user_id = connection.execute(
            text(
                """
                INSERT INTO core.app_user(login_id,password_hash,display_name,status)
                VALUES ('admin',:password,'관리자','active') RETURNING id
                """
            ),
            {"password": hash_password("correct horse battery staple")},
        ).scalar_one()
        workspace_id = connection.execute(
            text(
                """
                INSERT INTO core.workspace(owner_user_id,active_generation_id,workspace_kind)
                VALUES (:user,NULL,'MEMBER') RETURNING id
                """
            ),
            {"user": user_id},
        ).scalar_one()
        generation_id = connection.execute(
            text(
                """
                INSERT INTO core.data_generation
                  (workspace_id,seed_version,seed_date,activated_at,status)
                VALUES (:w,'member-test','2026-09-24',now(),'active') RETURNING id
                """
            ),
            {"w": workspace_id},
        ).scalar_one()
        connection.execute(
            text("UPDATE core.workspace SET active_generation_id=:g WHERE id=:w"),
            {"g": generation_id, "w": workspace_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO core.workspace_module(workspace_id,module_key,enabled)
                SELECT :w,module,true FROM unnest(ARRAY['core','mes','erp','fems']) module
                """
            ),
            {"w": workspace_id},
        )
        role_id = connection.execute(
            text(
                "INSERT INTO core.role(role_key,description) VALUES ('ADMIN','관리자') RETURNING id"
            )
        ).scalar_one()
        connection.execute(
            text("INSERT INTO core.user_role(user_id,role_id) VALUES (:u,:r)"),
            {"u": user_id, "r": role_id},
        )
    return user_id, workspace_id


@dataclass
class CommonEnv:
    engine: Engine
    user_id: int
    member_workspace: int
    app: object


@pytest.fixture(scope="module")
def common_env(db_engine: Engine) -> Generator[CommonEnv]:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ["SESSION_SECRET"] = "fs016-test-secret-that-is-longer-than-32-bytes"
    reset_engine()

    with db_engine.begin() as connection:
        tables = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspect(connection).get_table_names(schema=schema)
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )
        create_template(connection, date(2026, 9, 24))

    user_id, member_workspace = _create_member(db_engine)
    app = create_app()

    yield CommonEnv(
        engine=db_engine,
        user_id=user_id,
        member_workspace=member_workspace,
        app=app,
    )

    with db_engine.begin() as connection:
        tables = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspect(connection).get_table_names(schema=schema)
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )


def _create_guest(
    app: object, idempotency_key: str = "guest-create"
) -> tuple[TestClient, dict, str, str]:
    guest = TestClient(app, base_url="https://testserver")
    created = guest.post(
        "/api/v1/core/guest-sessions",
        headers={"Idempotency-Key": idempotency_key},
    )
    assert created.status_code == 201
    guest_data = created.json()["data"]
    guest_token = guest.cookies["fs_session"]
    guest_csrf = guest_data["csrfToken"]
    return guest, guest_data, guest_token, guest_csrf


def _login_member(
    app: object, idempotency_key: str = "member-login"
) -> tuple[TestClient, dict, str]:
    member = TestClient(app, base_url="https://testserver")
    login = member.post(
        "/api/v1/core/sessions",
        headers={"Idempotency-Key": idempotency_key},
        json={"loginId": "admin", "password": "correct horse battery staple"},
    )
    assert login.status_code == 201
    member_data = login.json()["data"]
    member_token = member.cookies["fs_session"]
    return member, member_data, member_token


def test_guest_entry_and_copy_count(common_env: CommonEnv) -> None:
    app = common_env.app
    engine = common_env.engine

    guest, guest_data, guest_token, guest_csrf = _create_guest(
        app, "guest-create-entry-count"
    )
    assert guest_token.startswith("g_")
    assert (
        _business_count(engine, guest_data["workspaceId"], guest_data["generationId"])
        == 7467
    )

    reset_headers = {
        "Idempotency-Key": "guest-reset-entry-count",
        "X-CSRF-Token": guest_csrf,
    }
    reset_first = guest.post(
        "/api/v1/core/workspace/generations", headers=reset_headers
    )
    assert reset_first.status_code == 201
    reset_generation_id = reset_first.json()["data"]["generationId"]
    assert reset_generation_id != guest_data["generationId"]
    assert (
        _business_count(engine, guest_data["workspaceId"], reset_generation_id) == 7467
    )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM core.data_generation WHERE id=:g"),
                {"g": guest_data["generationId"]},
            ).scalar_one()
            == "retired"
        )


def test_idempotency_identical_result(common_env: CommonEnv) -> None:
    app = common_env.app

    # 1) 게스트 세션 생성 멱등 재호출
    guest = TestClient(app, base_url="https://testserver")
    created = guest.post(
        "/api/v1/core/guest-sessions",
        headers={"Idempotency-Key": "guest-create-idem"},
    )
    assert created.status_code == 201
    replayed = guest.post(
        "/api/v1/core/guest-sessions",
        headers={"Idempotency-Key": "guest-create-idem"},
    )
    assert replayed.status_code == 201
    assert replayed.json() == created.json()

    guest_data = created.json()["data"]
    guest_csrf = guest_data["csrfToken"]

    # 2) 모듈 PATCH 멱등 재호출
    headers = {
        "X-CSRF-Token": guest_csrf,
        "Idempotency-Key": "module-mes-off-idem",
    }
    first = guest.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers,
        json={"enabled": False},
    )
    second = guest.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers,
        json={"enabled": False},
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

    # 3) 세대 재생성 멱등 재호출
    reset_headers = {
        "Idempotency-Key": "guest-reset-idem",
        "X-CSRF-Token": guest_csrf,
    }
    reset_first = guest.post(
        "/api/v1/core/workspace/generations", headers=reset_headers
    )
    reset_second = guest.post(
        "/api/v1/core/workspace/generations", headers=reset_headers
    )
    assert reset_first.status_code == reset_second.status_code == 201
    assert reset_first.json() == reset_second.json()

    # 4) 회원 로그인 멱등 재호출
    member = TestClient(app, base_url="https://testserver")
    member_login = member.post(
        "/api/v1/core/sessions",
        headers={"Idempotency-Key": "member-login-idem"},
        json={"loginId": "admin", "password": "correct horse battery staple"},
    )
    assert member_login.status_code == 201
    member_replay = member.post(
        "/api/v1/core/sessions",
        headers={"Idempotency-Key": "member-login-idem"},
        json={"loginId": "admin", "password": "correct horse battery staple"},
    )
    assert member_replay.status_code == 201
    assert member_replay.json() == member_login.json()


def test_idempotency_conflicting_payload_422(common_env: CommonEnv) -> None:
    app = common_env.app
    guest, _, _, guest_csrf = _create_guest(app, "guest-create-conflict")

    headers = {
        "X-CSRF-Token": guest_csrf,
        "Idempotency-Key": "module-mes-conflict-key",
    }
    first = guest.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers,
        json={"enabled": False},
    )
    assert first.status_code == 200

    conflict = guest.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers,
        json={"enabled": True},
    )
    assert conflict.status_code == 422
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_guest_scope_isolation(common_env: CommonEnv) -> None:
    app = common_env.app
    guest_a, _, _, guest_a_csrf = _create_guest(app, "guest-create-scope-a")
    guest_b, guest_b_data, _, _ = _create_guest(app, "guest-create-scope-b")

    modules_b_before = guest_b.get("/api/v1/core/workspace/modules").json()

    headers_a = {
        "X-CSRF-Token": guest_a_csrf,
        "Idempotency-Key": "module-mes-off-scope-a",
    }
    first = guest_a.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers_a,
        json={"enabled": False},
    )
    assert first.status_code == 200

    assert guest_b.get("/api/v1/core/workspace/modules").json() == modules_b_before
    assert (
        guest_b.get("/api/v1/core/workspace").json()["data"]["id"]
        == guest_b_data["workspaceId"]
    )


def test_token_kind_tampering_401(common_env: CommonEnv) -> None:
    app = common_env.app
    _, _, guest_token, _ = _create_guest(app, "guest-create-tamper")
    _, _, member_token = _login_member(app, "member-login-tamper")

    wrong_member_kind = TestClient(app, base_url="https://testserver")
    wrong_member_kind.cookies.set("fs_session", "m_" + guest_token[2:])
    assert wrong_member_kind.get("/api/v1/core/workspace").status_code == 401

    wrong_guest_kind = TestClient(app, base_url="https://testserver")
    wrong_guest_kind.cookies.set("fs_session", "g_" + member_token[2:])
    assert wrong_guest_kind.get("/api/v1/core/workspace").status_code == 401


def test_csrf_missing_and_mismatch_403(common_env: CommonEnv) -> None:
    app = common_env.app
    guest, _, _, _ = _create_guest(app, "guest-create-csrf")

    assert (
        guest.patch(
            "/api/v1/core/workspace/modules/erp",
            headers={"Idempotency-Key": "missing-csrf"},
            json={"enabled": False},
        ).status_code
        == 403
    )
    assert (
        guest.patch(
            "/api/v1/core/workspace/modules/erp",
            headers={"Idempotency-Key": "bad-csrf", "X-CSRF-Token": "wrong"},
            json={"enabled": False},
        ).status_code
        == 403
    )

    member, member_data, _ = _login_member(app, "member-login-csrf")

    assert (
        member.patch(
            "/api/v1/core/workspace/modules/erp",
            headers={"Idempotency-Key": "member-no-csrf"},
            json={"enabled": False},
        ).status_code
        == 403
    )
    assert (
        member.patch(
            "/api/v1/core/workspace/modules/erp",
            headers={"Idempotency-Key": "member-bad-csrf", "X-CSRF-Token": "wrong"},
            json={"enabled": False},
        ).status_code
        == 403
    )
    member_ok = member.patch(
        "/api/v1/core/workspace/modules/erp",
        headers={
            "Idempotency-Key": "member-erp-off",
            "X-CSRF-Token": member_data["csrfToken"],
        },
        json={"enabled": False},
    )
    assert member_ok.status_code == 200


def test_ended_guest_cookie_401(common_env: CommonEnv) -> None:
    app = common_env.app
    guest, _, guest_token, guest_csrf = _create_guest(app, "guest-create-ended")

    old_guest_cookie = guest_token
    logout_response = guest.delete(
        "/api/v1/core/sessions/current", headers={"X-CSRF-Token": guest_csrf}
    )
    assert logout_response.status_code == 204
    ended = TestClient(app, base_url="https://testserver")
    ended.cookies.set("fs_session", old_guest_cookie)
    assert ended.get("/api/v1/core/workspace").status_code == 401


def test_expired_cookie_410(common_env: CommonEnv) -> None:
    app = common_env.app
    engine = common_env.engine
    guest, guest_data, _, _ = _create_guest(app, "guest-create-expired")

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE core.workspace SET expires_at=:past WHERE id=:w"),
            {
                "past": datetime.now(UTC) - timedelta(seconds=1),
                "w": guest_data["workspaceId"],
            },
        )
    try:
        assert guest.get("/api/v1/core/workspace").status_code == 410
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE core.workspace SET expires_at=:future WHERE id=:w"),
                {
                    "future": datetime.now(UTC) + timedelta(days=1),
                    "w": guest_data["workspaceId"],
                },
            )


def test_cleanup_separates_data_and_audit(common_env: CommonEnv) -> None:
    app = common_env.app
    engine = common_env.engine
    with engine.begin() as connection:
        cleanup_expired_guests(connection)
    _, guest_data, _, _ = _create_guest(app, "guest-create-cleanup")

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE core.workspace SET expires_at=:past WHERE id=:w"),
            {
                "past": datetime.now(UTC) - timedelta(seconds=1),
                "w": guest_data["workspaceId"],
            },
        )
        cleaned = cleanup_expired_guests(connection)
    assert cleaned == 1
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM core.workspace WHERE id=:w"),
                {"w": guest_data["workspaceId"]},
            ).scalar_one()
            == 0
        )


def test_no_token_or_hash_in_logs_audit_receipts(
    common_env: CommonEnv, caplog: pytest.LogCaptureFixture
) -> None:
    app = common_env.app
    engine = common_env.engine

    caplog.set_level(logging.INFO, logger="factory_studio.request")

    guest, _, guest_token, guest_csrf = _create_guest(app, "guest-create-secrets")
    guest.patch(
        "/api/v1/core/workspace/modules/mes",
        headers={
            "X-CSRF-Token": guest_csrf,
            "Idempotency-Key": "module-mes-secrets",
        },
        json={"enabled": False},
    )
    member, member_data, member_token = _login_member(app, "member-login-secrets")
    member_ok = member.patch(
        "/api/v1/core/workspace/modules/erp",
        headers={
            "Idempotency-Key": "member-erp-off-secrets",
            "X-CSRF-Token": member_data["csrfToken"],
        },
        json={"enabled": False},
    )
    assert member_ok.status_code == 200

    sensitive = {
        guest_token,
        member_token,
        token_hash(guest_token),
        token_hash(member_token),
    }
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    with engine.connect() as connection:
        audit_text = "\n".join(
            str(value)
            for value in connection.execute(
                text("SELECT actor_key,summary::text FROM core.audit_event")
            ).tuples()
        )
        receipt_text = "\n".join(
            str(value)
            for value in connection.execute(
                text(
                    "SELECT actor_key,response_summary::text FROM core.request_receipt"
                )
            ).tuples()
        )
    for secret in sensitive:
        assert secret not in log_text
        assert secret not in audit_text
        assert secret not in receipt_text


def test_admin_access_and_guest_admin_404(common_env: CommonEnv) -> None:
    app = common_env.app
    member_workspace = common_env.member_workspace

    unknown = TestClient(app, base_url="https://testserver").get("/api/v1/core/unknown")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"

    member, member_data, member_token = _login_member(app, "member-login-admin-check")
    assert member_token.startswith("m_")
    assert member_data["workspaceId"] == member_workspace

    guest, _, _, _ = _create_guest(app, "guest-create-admin-check")

    assert member.get("/api/v1/core/admin/audit-events").status_code == 200
    assert guest.get("/api/v1/core/admin/audit-events").status_code == 404
