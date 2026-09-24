from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.common.security import hash_password, token_hash
from fs.core.service import cleanup_expired_guests
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, inspect, text


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


def test_fs016_guest_member_idempotency_isolation_and_cleanup(
    clean_database: Engine, caplog
) -> None:
    engine = clean_database
    with engine.begin() as connection:
        create_template(connection, date(2026, 9, 24))
    _user_id, member_workspace = _create_member(engine)

    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ["SESSION_SECRET"] = "fs016-test-secret-that-is-longer-than-32-bytes"
    reset_engine()
    caplog.set_level(logging.INFO, logger="factory_studio.request")
    app = create_app()
    unknown = TestClient(app, base_url="https://testserver").get("/api/v1/core/unknown")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"

    guest_a = TestClient(app, base_url="https://testserver")
    created_a = guest_a.post(
        "/api/v1/core/guest-sessions",
        headers={"Idempotency-Key": "guest-create-a"},
    )
    assert created_a.status_code == 201
    guest_a_data = created_a.json()["data"]
    guest_a_token = guest_a.cookies["fs_session"]
    guest_a_csrf = guest_a_data["csrfToken"]
    assert guest_a_token.startswith("g_")
    replayed_a = guest_a.post(
        "/api/v1/core/guest-sessions",
        headers={"Idempotency-Key": "guest-create-a"},
    )
    assert replayed_a.status_code == 201
    assert replayed_a.json() == created_a.json()
    assert (
        _business_count(
            engine, guest_a_data["workspaceId"], guest_a_data["generationId"]
        )
        == 7467
    )

    guest_b = TestClient(app, base_url="https://testserver")
    created_b = guest_b.post(
        "/api/v1/core/guest-sessions",
        headers={"Idempotency-Key": "guest-create-b"},
    )
    assert created_b.status_code == 201
    guest_b_data = created_b.json()["data"]
    modules_b_before = guest_b.get("/api/v1/core/workspace/modules").json()

    headers_a = {
        "X-CSRF-Token": guest_a_csrf,
        "Idempotency-Key": "module-mes-off-1",
    }
    first = guest_a.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers_a,
        json={"enabled": False},
    )
    second = guest_a.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers_a,
        json={"enabled": False},
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert guest_b.get("/api/v1/core/workspace/modules").json() == modules_b_before
    assert (
        guest_b.get("/api/v1/core/workspace").json()["data"]["id"]
        == guest_b_data["workspaceId"]
    )

    conflict = guest_a.patch(
        "/api/v1/core/workspace/modules/mes",
        headers=headers_a,
        json={"enabled": True},
    )
    assert conflict.status_code == 422
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert (
        guest_a.patch(
            "/api/v1/core/workspace/modules/erp",
            headers={"Idempotency-Key": "missing-csrf"},
            json={"enabled": False},
        ).status_code
        == 403
    )
    assert (
        guest_a.patch(
            "/api/v1/core/workspace/modules/erp",
            headers={"Idempotency-Key": "bad-csrf", "X-CSRF-Token": "wrong"},
            json={"enabled": False},
        ).status_code
        == 403
    )

    wrong_member_kind = TestClient(app, base_url="https://testserver")
    wrong_member_kind.cookies.set("fs_session", "m_" + guest_a_token[2:])
    assert wrong_member_kind.get("/api/v1/core/workspace").status_code == 401

    member = TestClient(app, base_url="https://testserver")
    member_login = member.post(
        "/api/v1/core/sessions",
        headers={"Idempotency-Key": "member-login-1"},
        json={"loginId": "admin", "password": "correct horse battery staple"},
    )
    assert member_login.status_code == 201
    member_data = member_login.json()["data"]
    member_token = member.cookies["fs_session"]
    assert member_token.startswith("m_")
    member_replay = member.post(
        "/api/v1/core/sessions",
        headers={"Idempotency-Key": "member-login-1"},
        json={"loginId": "admin", "password": "correct horse battery staple"},
    )
    assert member_replay.status_code == 201
    assert member_replay.json() == member_login.json()
    assert member_data["workspaceId"] == member_workspace
    assert member.get("/api/v1/core/admin/audit-events").status_code == 200
    assert guest_a.get("/api/v1/core/admin/audit-events").status_code == 404
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

    reset_headers = {
        "Idempotency-Key": "guest-reset-1",
        "X-CSRF-Token": guest_a_csrf,
    }
    reset_first = guest_a.post(
        "/api/v1/core/workspace/generations", headers=reset_headers
    )
    reset_second = guest_a.post(
        "/api/v1/core/workspace/generations", headers=reset_headers
    )
    assert reset_first.status_code == reset_second.status_code == 201
    assert reset_first.json() == reset_second.json()
    reset_generation_id = reset_first.json()["data"]["generationId"]
    assert reset_generation_id != guest_a_data["generationId"]
    assert (
        _business_count(engine, guest_a_data["workspaceId"], reset_generation_id)
        == 7467
    )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM core.data_generation WHERE id=:g"),
                {"g": guest_a_data["generationId"]},
            ).scalar_one()
            == "retired"
        )

    wrong_guest_kind = TestClient(app, base_url="https://testserver")
    wrong_guest_kind.cookies.set("fs_session", "g_" + member_token[2:])
    assert wrong_guest_kind.get("/api/v1/core/workspace").status_code == 401

    old_guest_cookie = guest_a_token
    logout_response = guest_a.delete(
        "/api/v1/core/sessions/current", headers={"X-CSRF-Token": guest_a_csrf}
    )
    assert logout_response.status_code == 204
    ended = TestClient(app, base_url="https://testserver")
    ended.cookies.set("fs_session", old_guest_cookie)
    assert ended.get("/api/v1/core/workspace").status_code == 401

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE core.workspace SET expires_at=:past WHERE id=:w"),
            {
                "past": datetime.now(UTC) - timedelta(seconds=1),
                "w": guest_a_data["workspaceId"],
            },
        )
        cleaned = cleanup_expired_guests(connection)
    assert cleaned == 1
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM core.workspace WHERE id=:w"),
                {"w": guest_a_data["workspaceId"]},
            ).scalar_one()
            == 0
        )

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE core.workspace SET expires_at=:past WHERE id=:w"),
            {
                "past": datetime.now(UTC) - timedelta(seconds=1),
                "w": guest_b_data["workspaceId"],
            },
        )
    assert guest_b.get("/api/v1/core/workspace").status_code == 410

    sensitive = {
        guest_a_token,
        member_token,
        token_hash(guest_a_token),
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
