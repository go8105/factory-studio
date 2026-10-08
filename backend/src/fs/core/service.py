from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any

from seed.copy import copy_template, copy_template_generation
from sqlalchemy import Connection, inspect, text

from fs.common.auth import AuthContext
from fs.common.clock import guest_expires_at
from fs.common.config import get_settings
from fs.common.errors import ApiError
from fs.common.idempotency import (
    find_receipt,
    request_digest,
    save_receipt,
)
from fs.common.modules import BUSINESS_SCHEMAS
from fs.common.security import (
    guest_csrf_token,
    hash_password,
    member_csrf_token,
    new_session_token,
    token_hash,
    verify_password,
)

GUEST_POOL_LOCK = 7_160_016


def _workspace_lock(connection: Connection, workspace_id: int) -> None:
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:namespace,:workspace)"),
        {"namespace": 16, "workspace": workspace_id},
    )


NICKNAME_DAYS = 90  # FS-027 D36: 별칭 보관 기간


def guest_nickname(value: str | None) -> str:
    """FS-027 D33: 앞뒤 공백을 지운 2~20자. 실명 대신 별칭을 받는다."""
    nickname = (value or "").strip()
    if not 2 <= len(nickname) <= 20:
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "별칭을 2~20자로 입력하세요.",
            {"fields": {"nickname": "별칭을 2~20자로 입력하세요."}},
        )
    return nickname


def create_guest(
    connection: Connection, target_date: date, idempotency_key: str, nickname: str
) -> tuple[dict[str, Any], str]:
    settings = get_settings()
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": GUEST_POOL_LOCK}
    )
    count = connection.execute(
        text("SELECT count(*) FROM core.workspace WHERE workspace_kind='GUEST'")
    ).scalar_one()
    if count >= settings.guest_limit:
        raise ApiError(429, "RATE_LIMITED", "게스트 공간 상한에 도달했습니다.")
    template = (
        connection.execute(
            text(
                """
            SELECT w.id workspace_id,g.id generation_id
            FROM core.workspace w
            JOIN core.data_generation g ON g.workspace_id=w.id
            WHERE w.workspace_kind='TEMPLATE' AND g.status='active'
              AND w.active_generation_id=g.id
            ORDER BY g.created_at DESC,g.id DESC LIMIT 1
            FOR SHARE OF w,g
                """
            )
        )
        .mappings()
        .one_or_none()
    )
    if template is None:
        raise ApiError(409, "PRECONDITION_NOT_MET", "활성 템플릿이 없습니다.")
    token = new_session_token("g")
    workspace_id, generation_id, _counts, _elapsed = copy_template(
        connection,
        template["workspace_id"],
        template["generation_id"],
        target_date,
        token_hash(token),
        schemas=(),  # W0-1: 솔루션 시드는 처음 열 때(seed_ready)
    )
    # 복사는 데이터 기준일(target_date)로 만료를 정한다. 만료는 실제 시간이어야 하므로 다시 쓴다.
    # FS_TODAY가 없으면 두 날짜가 같아 값이 바뀌지 않는다.
    connection.execute(
        text("UPDATE core.workspace SET expires_at=:expires WHERE id=:id"),
        {"expires": guest_expires_at(), "id": workspace_id},
    )
    workspace = (
        connection.execute(
            text(
                "SELECT guest_actor_key::text actor_key,expires_at FROM core.workspace WHERE id=:id"
            ),
            {"id": workspace_id},
        )
        .mappings()
        .one()
    )
    csrf = guest_csrf_token(settings.session_secret, token)
    data = {
        "actorKind": "GUEST",
        "workspaceId": workspace_id,
        "generationId": generation_id,
        "expiresAt": workspace["expires_at"].isoformat(),
        "csrfToken": csrf,
    }
    context = AuthContext(
        actor_kind="GUEST",
        actor_key=workspace["actor_key"],
        workspace_id=workspace_id,
        generation_id=generation_id,
        user_id=None,
        roles=frozenset({"GUEST"}),
        token=token,
    )
    save_receipt(
        connection,
        context,
        "guest.session.create",
        idempotency_key,
        request_digest({"nickname": nickname}),
        "workspace",
        workspace_id,
        {key: value for key, value in data.items() if key != "csrfToken"},
        201,
    )
    _audit(
        connection,
        workspace_id,
        "GUEST",
        workspace["actor_key"],
        None,
        "guest_session.created",
        "workspace",
        str(workspace_id),
        {"nickname": nickname},
    )
    return data, token


def login_member(
    connection: Connection, login_id: str, password: str, idempotency_key: str
) -> tuple[dict[str, Any], str]:
    row = (
        connection.execute(
            text(
                """
            SELECT u.id,u.password_hash,u.display_name,w.id workspace_id,
                   w.active_generation_id,
                   array_remove(array_agg(r.role_key),NULL) roles
            FROM core.app_user u
            JOIN core.workspace w ON w.owner_user_id=u.id AND w.workspace_kind='MEMBER'
            LEFT JOIN core.user_role ur ON ur.user_id=u.id
            LEFT JOIN core.role r ON r.id=ur.role_id
            WHERE u.login_id=:login AND u.status='active' AND u.disabled_at IS NULL
            GROUP BY u.id,u.password_hash,u.display_name,w.id,w.active_generation_id
            """
            ),
            {"login": login_id.strip().lower()},
        )
        .mappings()
        .one_or_none()
    )
    if row is None or not verify_password(password, row["password_hash"]):
        # 세션 만료(SESSION_EXPIRED)와 구분한다. 아이디가 없는지·비밀번호가 틀렸는지는 알려 주지 않는다.
        raise ApiError(
            401, "INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않습니다."
        )
    token = new_session_token("m")
    csrf = member_csrf_token(get_settings().session_secret, token)
    expires = datetime.now(UTC) + timedelta(minutes=get_settings().session_idle_minutes)
    connection.execute(
        text(
            """
            INSERT INTO core.auth_session(user_id,token_hash,csrf_token_hash,expires_at)
            VALUES (:user,:token,:csrf,:expires)
            """
        ),
        {
            "user": row["id"],
            "token": token_hash(token),
            "csrf": token_hash(csrf),
            "expires": expires,
        },
    )
    _audit(
        connection,
        row["workspace_id"],
        "MEMBER",
        str(row["id"]),
        row["id"],
        "member_session.created",
        "app_user",
        str(row["id"]),
    )
    data = {
        "actorKind": "MEMBER",
        "workspaceId": row["workspace_id"],
        "generationId": row["active_generation_id"],
        "displayName": row["display_name"],
        "roles": row["roles"],
        "expiresAt": expires.isoformat(),
        "csrfToken": csrf,
    }
    context = AuthContext(
        actor_kind="MEMBER",
        actor_key=str(row["id"]),
        workspace_id=row["workspace_id"],
        generation_id=row["active_generation_id"],
        user_id=row["id"],
        roles=frozenset(row["roles"]),
        token=token,
    )
    save_receipt(
        connection,
        context,
        "member.session.create",
        idempotency_key,
        request_digest({"loginId": login_id.strip().lower(), "password": password}),
        "auth_session",
        connection.execute(
            text("SELECT id FROM core.auth_session WHERE token_hash=:token"),
            {"token": token_hash(token)},
        ).scalar_one(),
        {key: value for key, value in data.items() if key != "csrfToken"},
        201,
    )
    return data, token


def create_member_account(
    connection: Connection,
    login_id: str,
    display_name: str,
    password: str,
    target_date: date,
    admin: bool = False,
) -> dict[str, Any]:
    """회원 계정 + 회원 공간 + 템플릿 세대 복사를 한 트랜잭션에서 만든다(tools/create_member.py).

    제품에는 회원가입이 없다. 운영자가 서버에서 직접 실행한다. 비밀번호는 해시만 저장한다.
    """
    login_id = login_id.strip().lower()
    if not login_id or len(password) < 10:
        raise ValueError("아이디가 비었거나 비밀번호가 10자 미만입니다.")
    exists = connection.execute(
        text("SELECT 1 FROM core.app_user WHERE login_id=:login"), {"login": login_id}
    ).first()
    if exists:
        raise ValueError(f"이미 있는 아이디입니다: {login_id}")
    template = (
        connection.execute(
            text(
                """
            SELECT w.id workspace_id,g.id generation_id
            FROM core.workspace w JOIN core.data_generation g ON g.workspace_id=w.id
            WHERE w.workspace_kind='TEMPLATE' AND w.active_generation_id=g.id
              AND g.status='active'
            ORDER BY g.created_at DESC,g.id DESC LIMIT 1
                """
            )
        )
        .mappings()
        .one_or_none()
    )
    if template is None:
        raise ValueError("활성 템플릿이 없습니다. seed.cli template을 먼저 실행하세요.")
    user_id = connection.execute(
        text(
            "INSERT INTO core.app_user(login_id,password_hash,display_name,status) "
            "VALUES (:login,:hash,:name,'active') RETURNING id"
        ),
        {"login": login_id, "hash": hash_password(password), "name": display_name},
    ).scalar_one()
    workspace_id = connection.execute(
        text(
            "INSERT INTO core.workspace(owner_user_id,active_generation_id,workspace_kind) "
            "VALUES (:user,NULL,'MEMBER') RETURNING id"
        ),
        {"user": user_id},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO core.workspace_module(workspace_id,module_key,enabled) "
            "SELECT :w,m,true FROM unnest(ARRAY['core','mes','erp','fems','qms','wms','bems','spc','gw','cmms','hr']) m"
        ),
        {"w": workspace_id},
    )
    if admin:
        role_id = (
            connection.execute(
                text("SELECT id FROM core.role WHERE role_key='ADMIN'")
            ).scalar()
            or connection.execute(
                text(
                    "INSERT INTO core.role(role_key,description) VALUES ('ADMIN','관리자') "
                    "RETURNING id"
                )
            ).scalar_one()
        )
        connection.execute(
            text("INSERT INTO core.user_role(user_id,role_id) VALUES (:u,:r)"),
            {"u": user_id, "r": role_id},
        )
    generation_id, counts, _ = copy_template_generation(
        connection,
        template["workspace_id"],
        template["generation_id"],
        workspace_id,
        target_date,
        schemas=(),  # W0-1 지연 복사
    )
    return {
        "userId": user_id,
        "loginId": login_id,
        "workspaceId": workspace_id,
        "generationId": generation_id,
        "copiedRows": sum(counts.values()),
        "admin": admin,
    }


def current_session(connection: Connection, context: AuthContext) -> dict[str, Any]:
    _workspace_lock(connection, context.workspace_id)
    workspace = (
        connection.execute(
            text(
                "SELECT workspace_kind,expires_at FROM core.workspace WHERE id=:id AND active_generation_id=:g"
            ),
            {"id": context.workspace_id, "g": context.generation_id},
        )
        .mappings()
        .one()
    )
    return {
        "actorKind": context.actor_kind,
        "workspaceId": context.workspace_id,
        "generationId": context.generation_id,
        "userId": context.user_id,
        "roles": sorted(context.roles),
        "expiresAt": workspace["expires_at"].isoformat()
        if workspace["expires_at"]
        else None,
    }


def logout(connection: Connection, context: AuthContext) -> None:
    _workspace_lock(connection, context.workspace_id)
    if context.actor_kind == "GUEST":
        # 별도 revoked_at이 없으므로 새 난수 해시로 교체하고 활성 토큰 형식에서 제외한다.
        replacement = "revoked_" + token_hash(secrets.token_urlsafe(32))
        result = connection.execute(
            text(
                "UPDATE core.workspace SET guest_session_key=:replacement WHERE id=:id AND guest_session_key=:current"
            ),
            {
                "replacement": replacement,
                "id": context.workspace_id,
                "current": token_hash(context.token),
            },
        )
    else:
        result = connection.execute(
            text(
                "UPDATE core.auth_session SET revoked_at=now() WHERE token_hash=:token AND revoked_at IS NULL"
            ),
            {"token": token_hash(context.token)},
        )
    if result.rowcount != 1:
        raise ApiError(401, "SESSION_EXPIRED", "이미 종료된 세션입니다.")
    _audit(
        connection,
        context.workspace_id,
        context.actor_kind,
        context.actor_key,
        context.user_id,
        "session.revoked",
        "workspace",
        str(context.workspace_id),
    )


def workspace_info(connection: Connection, context: AuthContext) -> dict[str, Any]:
    _workspace_lock(connection, context.workspace_id)
    row = (
        connection.execute(
            text(
                """
            SELECT id,workspace_kind,config_version,energy_input_revision,created_at,expires_at
            FROM core.workspace WHERE id=:id AND active_generation_id=:g
            """
            ),
            {"id": context.workspace_id, "g": context.generation_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "공간을 찾을 수 없습니다.")
    return {
        "id": row["id"],
        "workspaceKind": row["workspace_kind"],
        "configVersion": row["config_version"],
        "energyInputRevision": row["energy_input_revision"],
        "createdAt": row["created_at"].isoformat(),
        "expiresAt": row["expires_at"].isoformat() if row["expires_at"] else None,
    }


def list_modules(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    _workspace_lock(connection, context.workspace_id)
    rows = connection.execute(
        text(
            "SELECT module_key,enabled,updated_at FROM core.workspace_module WHERE workspace_id=:w ORDER BY module_key"
        ),
        {"w": context.workspace_id},
    ).mappings()
    return [
        {
            "moduleKey": row["module_key"],
            "enabled": row["enabled"],
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
        for row in rows
    ]


def list_admin_records(
    connection: Connection,
    context: AuthContext,
    resource: str,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    if "ADMIN" not in context.roles:
        if context.actor_kind == "GUEST":
            raise ApiError(404, "NOT_FOUND", "대상을 찾을 수 없습니다.")
        raise ApiError(403, "FORBIDDEN", "관리자 권한이 필요합니다.")
    if resource == "job-runs":
        table = "core.job_run"
        columns = "id,job_kind,status,scope_kind,started_at,finished_at"
    elif resource == "audit-events":
        table = "core.audit_event"
        columns = "id,action,entity_kind,entity_key,actor_kind,created_at"
    elif resource == "guest-visits":
        # FS-027 D35: 게스트 접속 = 생성 감사 기록. 정리된 공간은 스냅샷 번호로 남는다.
        table = "core.audit_event WHERE action='guest_session.created'"
        columns = (
            "id,created_at,summary->>'nickname' nickname,"
            "coalesce(workspace_id,workspace_snapshot_id) workspace_no,"
            "scope_kind='RETIRED' retired"
        )
    else:
        raise ValueError("unknown admin resource")
    total = connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
    rows = connection.execute(
        text(
            f"SELECT {columns} FROM {table} ORDER BY id DESC OFFSET :offset LIMIT :limit"
        ),
        {"offset": offset, "limit": limit},
    ).mappings()
    data = []
    for row in rows:
        data.append(
            {
                _camel(key): value.isoformat() if isinstance(value, datetime) else value
                for key, value in row.items()
            }
        )
    return data, total


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


def update_module(
    connection: Connection,
    context: AuthContext,
    module_key: str,
    enabled: bool,
    idempotency_key: str,
) -> dict[str, Any]:
    if module_key == "core" and not enabled:
        raise ApiError(409, "PRECONDITION_NOT_MET", "core 모듈은 끌 수 없습니다.")
    _workspace_lock(connection, context.workspace_id)
    digest = request_digest({"enabled": enabled})
    cached = find_receipt(
        connection, context, "workspace.module.update", idempotency_key, digest
    )
    if cached is not None:
        return cached
    row = (
        connection.execute(
            text(
                """
            UPDATE core.workspace_module SET enabled=:enabled,updated_at=now()
            WHERE workspace_id=:w AND module_key=:module
            RETURNING id,module_key,enabled,updated_at
            """
            ),
            {"enabled": enabled, "w": context.workspace_id, "module": module_key},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "모듈을 찾을 수 없습니다.")
    response = {
        "moduleKey": row["module_key"],
        "enabled": row["enabled"],
        "updatedAt": row["updated_at"].isoformat(),
    }
    save_receipt(
        connection,
        context,
        "workspace.module.update",
        idempotency_key,
        digest,
        "workspace_module",
        row["id"],
        response,
    )
    _audit(
        connection,
        context.workspace_id,
        context.actor_kind,
        context.actor_key,
        context.user_id,
        "workspace_module.updated",
        "workspace_module",
        str(row["id"]),
        {"moduleKey": module_key, "enabled": enabled},
    )
    return response


def reset_generation(
    connection: Connection,
    context: AuthContext,
    target_date: date,
    idempotency_key: str,
) -> dict[str, Any]:
    _workspace_lock(connection, context.workspace_id)
    digest = request_digest({"targetDate": target_date.isoformat()})
    cached = find_receipt(
        connection, context, "workspace.generation.reset", idempotency_key, digest
    )
    if cached is not None:
        return cached
    template = (
        connection.execute(
            text(
                """
            SELECT w.id workspace_id,g.id generation_id
            FROM core.workspace w JOIN core.data_generation g ON g.workspace_id=w.id
            WHERE w.workspace_kind='TEMPLATE' AND w.active_generation_id=g.id
              AND g.status='active'
            ORDER BY g.created_at DESC,g.id DESC LIMIT 1 FOR SHARE OF w,g
                """
            )
        )
        .mappings()
        .one_or_none()
    )
    if template is None:
        raise ApiError(409, "PRECONDITION_NOT_MET", "활성 템플릿이 없습니다.")
    generation_id, counts, elapsed = copy_template_generation(
        connection,
        template["workspace_id"],
        template["generation_id"],
        context.workspace_id,
        target_date,
        schemas=(),  # W0-1 지연 복사
    )
    response = {
        "generationId": generation_id,
        "seedDate": target_date.isoformat(),
        "copiedRows": sum(counts.values()),
        "elapsedSeconds": round(elapsed, 6),
    }
    new_context = AuthContext(
        actor_kind=context.actor_kind,
        actor_key=context.actor_key,
        workspace_id=context.workspace_id,
        generation_id=generation_id,
        user_id=context.user_id,
        roles=context.roles,
        token=context.token,
    )
    save_receipt(
        connection,
        new_context,
        "workspace.generation.reset",
        idempotency_key,
        digest,
        "data_generation",
        generation_id,
        response,
        201,
    )
    _audit(
        connection,
        context.workspace_id,
        context.actor_kind,
        context.actor_key,
        context.user_id,
        "workspace_generation.reset",
        "data_generation",
        str(generation_id),
        {"seedDate": target_date.isoformat()},
    )
    return response


def cleanup_expired_guests(connection: Connection) -> int:
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": GUEST_POOL_LOCK}
    )
    candidates = (
        connection.execute(
            text(
                """
            SELECT id FROM core.workspace
            WHERE workspace_kind='GUEST' AND expires_at<=now()
            ORDER BY id FOR UPDATE SKIP LOCKED
                """
            )
        )
        .scalars()
        .all()
    )
    for workspace_id in candidates:
        _workspace_lock(connection, workspace_id)
        _delete_guest(connection, workspace_id)
    # FS-027 D36: 감사 기록 불변 정책의 유일한 예외 — 보관 기간이 지난 접속 기록의 별칭만 지운다.
    connection.execute(
        text(
            "UPDATE core.audit_event SET summary = summary - 'nickname' "
            "WHERE action='guest_session.created' AND summary ? 'nickname' "
            "AND created_at < now() - make_interval(days => :days)"
        ),
        {"days": NICKNAME_DAYS},
    )
    return len(candidates)


def _delete_guest(connection: Connection, workspace_id: int) -> None:
    generation_ids = (
        connection.execute(
            text("SELECT id FROM core.data_generation WHERE workspace_id=:w"),
            {"w": workspace_id},
        )
        .scalars()
        .all()
    )
    order, cut = _cleanup_plan(connection)
    for table_name, columns in cut:
        connection.execute(
            text(
                f"UPDATE {table_name} SET "
                + ",".join(f"{c}=NULL" for c in columns)
                + " WHERE workspace_id=:w"
            ),
            {"w": workspace_id},
        )
    for table_name in reversed(order):
        schema, table = table_name.split(".")
        connection.execute(
            text(f'DELETE FROM "{schema}"."{table}" WHERE workspace_id=:w'),
            {"w": workspace_id},
        )
    connection.execute(
        text("DELETE FROM core.holiday WHERE workspace_id=:w"),
        {"w": workspace_id},
    )
    connection.execute(
        text("DELETE FROM core.request_receipt WHERE workspace_id=:w"),
        {"w": workspace_id},
    )
    connection.execute(
        text("DELETE FROM core.workspace_module WHERE workspace_id=:w"),
        {"w": workspace_id},
    )
    connection.execute(
        text(
            """
            UPDATE core.audit_event SET workspace_id=NULL,job_run_id=NULL,
              scope_kind='RETIRED',workspace_snapshot_id=:w
            WHERE workspace_id=:w
            """
        ),
        {"w": workspace_id},
    )
    connection.execute(
        text(
            """
            UPDATE core.job_run SET workspace_id=NULL,target_generation_id=NULL,
              scope_kind='RETIRED',workspace_snapshot_id=:w,
              generation_snapshot_id=COALESCE(generation_snapshot_id,:g)
            WHERE workspace_id=:w
            """
        ),
        {"w": workspace_id, "g": generation_ids[0] if generation_ids else None},
    )
    connection.execute(
        text("UPDATE core.workspace SET active_generation_id=NULL WHERE id=:w"),
        {"w": workspace_id},
    )
    connection.execute(
        text("DELETE FROM core.data_generation WHERE workspace_id=:w"),
        {"w": workspace_id},
    )
    connection.execute(
        text("DELETE FROM core.workspace WHERE id=:w"), {"w": workspace_id}
    )


def _cleanup_plan(
    connection: Connection,
) -> tuple[list[str], list[tuple[str, tuple[str, ...]]]]:
    """(지우는 순서, 먼저 비울 FK 칼럼).

    MES 재작업 지시(work_order → lot)와 LOT(lot → work_order)처럼 **서로를 가리키는 고리**가 있어
    순서만으로는 지울 수 없다. 고리에 들어간 FK 중 비울 수 있는 칼럼만 먼저 비워 고리를 끊는다.
    고리 밖의 FK는 건드리지 않는다 — 비우면 다른 CHECK가 깨진다.
    """
    inspector = inspect(connection)
    tables = {
        f"{schema}.{table}"
        for schema in BUSINESS_SCHEMAS
        for table in inspector.get_table_names(schema=schema)
    }
    links: dict[str, dict[str, tuple[str, ...]]] = {}
    dependencies: dict[str, set[str]] = {}
    for table_name in tables:
        schema, table = table_name.split(".")
        nullable = {
            column["name"]
            for column in inspector.get_columns(table, schema=schema)
            if column["nullable"]
        }
        targets: set[str] = set()
        breakable: dict[str, tuple[str, ...]] = {}
        for fk in inspector.get_foreign_keys(table, schema=schema):
            target = f"{fk['referred_schema']}.{fk['referred_table']}"
            if target not in tables or target == table_name:
                continue
            targets.add(target)
            columns = tuple(c for c in fk["constrained_columns"] if c in nullable)
            if columns:
                breakable[target] = columns
        dependencies[table_name] = targets
        links[table_name] = breakable

    ordered: list[str] = []
    cut: list[tuple[str, tuple[str, ...]]] = []
    remaining = set(tables)
    while remaining:
        ready = sorted(t for t in remaining if not (dependencies[t] & remaining))
        if not ready:
            # 남은 것이 고리다. 고리 안을 가리키는 비울 수 있는 FK만 끊는다.
            broken = {
                table: tuple(
                    column
                    for target, columns in links[table].items()
                    if target in remaining
                    for column in columns
                )
                for table in sorted(remaining)
            }
            ready = sorted(t for t, columns in broken.items() if columns)
            if not ready:
                raise RuntimeError(f"guest cleanup FK cycle: {sorted(remaining)}")
            cut += [(t, broken[t]) for t in ready]
            for table in ready:
                # 끊은 고리만 지운다 — 비울 수 없는 의존은 그대로 둬야 순서가 맞다.
                dependencies[table] -= {
                    target for target in links[table] if target in remaining
                }
            continue
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered, cut


def _business_table_order(connection: Connection) -> list[str]:
    return _cleanup_plan(connection)[0]


def _audit(
    connection: Connection,
    workspace_id: int,
    actor_kind: str,
    actor_key: str,
    actor_user_id: int | None,
    action: str,
    entity_kind: str,
    entity_key: str,
    summary: dict[str, Any] | None = None,
) -> None:
    import json

    connection.execute(
        text(
            """
            INSERT INTO core.audit_event
              (workspace_id,actor_user_id,action,entity_kind,entity_key,summary,
               actor_kind,actor_key,scope_kind)
            VALUES (:w,:user,:action,:entity,:entity_key,CAST(:summary AS jsonb),
                    :kind,:actor,'WORKSPACE')
            """
        ),
        {
            "w": workspace_id,
            "user": actor_user_id,
            "action": action,
            "entity": entity_kind,
            "entity_key": entity_key,
            "summary": json.dumps(summary or {}, ensure_ascii=False),
            "kind": actor_kind,
            "actor": actor_key,
        },
    )
