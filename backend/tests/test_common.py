from __future__ import annotations

import logging
import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.common.security import hash_password, token_hash
from fs.core.service import cleanup_expired_guests
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, inspect, text

SOLUTION_PAGES = {
    "mes": "/api/v1/mes/work-orders",
    "erp": "/api/v1/erp/partners",
    "fems": "/api/v1/fems/energy-sources",
    "qms": "/api/v1/qms/dashboard",
    "wms": "/api/v1/wms/dashboard",
    "bems": "/api/v1/bems/dashboard",
    "spc": "/api/v1/spc/dashboard",
    "gw": "/api/v1/gw/dashboard",
}


def _open_all_solutions(client: TestClient) -> None:
    for path in SOLUTION_PAGES.values():
        assert client.get(path).status_code == 200, path
    # CMMS는 아직 API가 없다(W3). 시드도 없으므로 행 수에 영향 없다.


def _schema_count(
    engine: Engine, schema: str, workspace_id: int, generation_id: int
) -> int:
    with engine.connect() as connection:
        return sum(
            connection.execute(
                text(
                    f'SELECT count(*) FROM "{schema}"."{table}" WHERE workspace_id=:w AND generation_id=:g'
                ),
                {"w": workspace_id, "g": generation_id},
            ).scalar_one()
            for table in inspect(connection).get_table_names(schema=schema)
        )


def _business_count(engine: Engine, workspace_id: int, generation_id: int) -> int:
    total = 0
    with engine.connect() as connection:
        for schema in ("mes", "erp", "fems", "qms", "wms", "bems", "spc", "gw", "cmms"):
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
            for schema in (
                "core",
                "mes",
                "erp",
                "fems",
                "qms",
                "wms",
                "bems",
                "spc",
                "gw",
                "cmms",
            )
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
            for schema in (
                "core",
                "mes",
                "erp",
                "fems",
                "qms",
                "wms",
                "bems",
                "spc",
                "gw",
                "cmms",
            )
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
        json={"nickname": "테스트 게스트"},
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
    workspace_id, generation_id = guest_data["workspaceId"], guest_data["generationId"]
    # W0-1 지연 복사: 만들 때는 모듈 행 10개만, 솔루션은 처음 열 때 그 시드만 복사한다.
    assert _business_count(engine, workspace_id, generation_id) == 10
    assert guest.get("/api/v1/qms/dashboard").status_code == 200
    assert _schema_count(engine, "qms", workspace_id, generation_id) > 0
    assert _schema_count(engine, "mes", workspace_id, generation_id) == 0
    _open_all_solutions(guest)
    # FS-028c SPC 시드 +2,752, gw·cmms 모듈 행 +2 → 14,685 (모두 열면 예전 전체 복사와 같다)
    assert _business_count(engine, workspace_id, generation_id) == 14685
    _open_all_solutions(guest)  # 두 번 열어도 다시 복사하지 않는다
    assert _business_count(engine, workspace_id, generation_id) == 14685

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
    assert _business_count(engine, workspace_id, reset_generation_id) == 10
    _open_all_solutions(guest)
    assert _business_count(engine, workspace_id, reset_generation_id) == 14685
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
        json={"nickname": "테스트 게스트"},
        headers={"Idempotency-Key": "guest-create-idem"},
    )
    assert created.status_code == 201
    replayed = guest.post(
        "/api/v1/core/guest-sessions",
        json={"nickname": "테스트 게스트"},
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


# ---- FS-027 게스트 별칭과 접속 이력 (AC-165~169) ----
def _guest_post(app: object, key: str, body: object) -> object:
    return TestClient(app, base_url="https://testserver").post(
        "/api/v1/core/guest-sessions", json=body, headers={"Idempotency-Key": key}
    )


def _guest_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT count(*) FROM core.workspace WHERE workspace_kind='GUEST'")
        ).scalar_one()


def test_guest_requires_nickname(common_env: CommonEnv) -> None:
    """AC-165: 별칭 없음·공백만·1자·21자는 400이고 공간을 만들지 않는다."""
    before = _guest_count(common_env.engine)
    for i, body in enumerate(
        [None, {}, {"nickname": "   "}, {"nickname": "가"}, {"nickname": "가" * 21}]
    ):
        response = _guest_post(common_env.app, f"nick-bad-{i}", body)
        assert response.status_code == 400, body
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_FAILED"
        assert "nickname" in error["details"]["fields"]
    assert _guest_count(common_env.engine) == before


def test_guest_nickname_is_audited_and_idempotent(common_env: CommonEnv) -> None:
    """AC-166·167: 공백을 지운 별칭이 접속 기록에 남고, 같은 키·다른 별칭은 422."""
    app = common_env.app
    guest = TestClient(app, base_url="https://testserver")
    first = guest.post(
        "/api/v1/core/guest-sessions",
        json={"nickname": "  평가자 A  "},
        headers={"Idempotency-Key": "nick-idem"},
    )
    assert first.status_code == 201
    workspace_id = first.json()["data"]["workspaceId"]
    again = guest.post(
        "/api/v1/core/guest-sessions",
        json={"nickname": "평가자 A"},
        headers={"Idempotency-Key": "nick-idem"},
    )
    assert again.status_code == 201 and again.json() == first.json()
    other = guest.post(
        "/api/v1/core/guest-sessions",
        json={"nickname": "평가자 B"},
        headers={"Idempotency-Key": "nick-idem"},
    )
    assert other.status_code == 422
    with common_env.engine.connect() as connection:
        summaries = (
            connection.execute(
                text(
                    "SELECT summary FROM core.audit_event WHERE action='guest_session.created' "
                    "AND workspace_id=:w"
                ),
                {"w": workspace_id},
            )
            .scalars()
            .all()
        )
    assert summaries == [{"nickname": "평가자 A"}]


def test_admin_guest_visits_and_nickname_retention(common_env: CommonEnv) -> None:
    """AC-168·169: 관리자만 접속 이력을 보고, 정리된 공간도 남으며, 90일 뒤 별칭만 지운다."""
    app, engine = common_env.app, common_env.engine
    guest, data, _, _ = _create_guest(app, "nick-visit")
    workspace_id = data["workspaceId"]
    assert guest.get("/api/v1/core/admin/guest-visits").status_code == 404
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace SET expires_at=now() - interval '1 minute' WHERE id=:w"
            ),
            {"w": workspace_id},
        )
        cleanup_expired_guests(connection)
    member, _, _ = _login_member(app, "nick-visit-admin")
    visits = member.get("/api/v1/core/admin/guest-visits?limit=100").json()["data"]
    row = next(v for v in visits if v["workspaceNo"] == workspace_id)
    assert (row["nickname"], row["retired"]) == ("테스트 게스트", True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.audit_event SET created_at=now() - interval '91 days' WHERE id=:id"
            ),
            {"id": row["id"]},
        )
        cleanup_expired_guests(connection)
    visits = member.get("/api/v1/core/admin/guest-visits?limit=100").json()["data"]
    row = next(v for v in visits if v["id"] == row["id"])
    assert row["nickname"] is None and row["workspaceNo"] == workspace_id
