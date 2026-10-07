"""공통 엔진 — 기준정보(마스터) 조회·등록·수정·삭제 (DSN-01 C, W0-4).

솔루션은 표 하나를 `Master`로 **선언**하고, 자기 업무 규칙만 `check` 함수로 넘긴다.
반복되던 목록·단건·중복 검사·참조 확인·저장 SQL은 여기 한 벌만 둔다.

규칙(바꾸지 않는다): 모든 질의는 범위 S=(workspace_id, generation_id)로 한정한다.
표·칸 이름은 선언된 것만 쓴다(클라이언트 값이 SQL에 섞이지 않는다).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope

# 업무 규칙 훅: (연결, 범위, 합친 값, 현재 행 또는 None, 대상 id 또는 None)
Check = Callable[
    [Connection, AuthContext, dict[str, Any], dict[str, Any] | None, int | None], None
]


@dataclass(frozen=True)
class Reference:
    """이 행을 참조하는 곳. 하나라도 있으면 삭제를 막는다."""

    table: str  # "fems.meter_channel"
    column: str  # "energy_source_id"
    label: str  # 사용자에게 보여줄 이름


@dataclass(frozen=True)
class Master:
    module: str  # 모듈 키(스코프 확인에 쓴다)
    table: str  # "fems.energy_source"
    columns: tuple[str, ...]  # 저장·표시하는 칸(id·created_at 제외)
    sort: Mapping[str, str]  # 허용 정렬: 보이는 이름 → 칸
    default_sort: str  # "source_code ASC"
    unique: tuple[str, ...] = ()  # 이 칸 조합은 공간 안에서 유일
    references: tuple[Reference, ...] = ()
    not_found: str = "대상을 찾을 수 없습니다."
    duplicate_field: str = ""  # 중복일 때 가리킬 입력 칸(보이는 이름)
    duplicate_message: str = "이미 사용 중인 값입니다."
    referenced_message: str = "참조 중인 항목은 삭제할 수 없습니다."
    filters: Mapping[str, str] = field(default_factory=dict)  # 조회 조건: 이름 → 칸

    @property
    def entity(self) -> str:
        return self.table.split(".", 1)[1]

    @property
    def selection(self) -> str:
        return "id," + ",".join(self.columns) + ",created_at"


def camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.title() for part in rest)


def present(row: Mapping[str, Any]) -> dict[str, Any]:
    """DB 행 → 응답(JSON). 소수는 문자열, 날짜·시각은 ISO 문자열."""
    return {
        camel(key): str(value)
        if isinstance(value, Decimal)
        else value.isoformat()
        if isinstance(value, (date, datetime, time))
        else value
        for key, value in row.items()
    }


def _scope(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _not_found(master: Master) -> ApiError:
    return ApiError(404, "NOT_FOUND", master.not_found)


def order_by(master: Master, sort: str | None) -> str:
    if sort is None:
        return master.default_sort
    name, _, direction = sort.partition(":")
    column = master.sort.get(name)
    if column is None or direction not in ("asc", "desc"):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "정렬 조건이 올바르지 않습니다.",
            {"fields": {"sort": f"허용: {', '.join(master.sort)} (asc|desc)"}},
        )
    return f"{column} {direction.upper()}"


def fetch(
    connection: Connection, master: Master, scoped: AuthContext, row_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {master.selection} FROM {master.table} "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": row_id},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def references(
    connection: Connection, master: Master, scoped: AuthContext, row_id: int
) -> list[dict[str, Any]]:
    found = []
    for reference in master.references:
        count = connection.execute(
            text(
                f"SELECT count(*) FROM {reference.table} "
                f"WHERE workspace_id=:w AND generation_id=:g AND {reference.column}=:id"
            ),
            {**_scope(scoped), "id": row_id},
        ).scalar_one()
        if count:
            found.append(
                {"table": reference.table, "label": reference.label, "count": count}
            )
    return found


def duplicate(
    connection: Connection,
    master: Master,
    scoped: AuthContext,
    values: Mapping[str, Any],
    row_id: int | None,
) -> bool:
    if not master.unique:
        return False
    where = " AND ".join(f"{column}=:{column}" for column in master.unique)
    return (
        connection.execute(
            text(
                f"SELECT 1 FROM {master.table} WHERE workspace_id=:w AND generation_id=:g "
                f"AND {where} AND id IS DISTINCT FROM :id"
            ),
            {
                **_scope(scoped),
                **{column: values[column] for column in master.unique},
                "id": row_id,
            },
        ).first()
        is not None
    )


def store(
    connection: Connection,
    master: Master,
    scoped: AuthContext,
    values: Mapping[str, Any],
    row_id: int | None,
) -> dict[str, Any]:
    assert set(values) <= set(master.columns), set(values) - set(master.columns)
    if row_id is None:
        names = ",".join(values)
        binds = ",".join(":" + name for name in values)
        sql = (
            f"INSERT INTO {master.table} (workspace_id,generation_id,{names}) "
            f"VALUES (:w,:g,{binds})"
        )
    else:
        assignments = ",".join(f"{name}=:{name}" for name in values)
        sql = (
            f"UPDATE {master.table} SET {assignments} "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        )
    row = (
        connection.execute(
            text(f"{sql} RETURNING {master.selection}"),
            {**_scope(scoped), **values, "id": row_id},
        )
        .mappings()
        .one()
    )
    return present(row)


# ── 바깥에서 쓰는 다섯 가지 ────────────────────────────────────────────────────


def listing(
    master: Master,
    context: AuthContext,
    *,
    filters: Mapping[str, Any] | None = None,
    sort: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    order = order_by(master, sort)
    where = "workspace_id=:w AND generation_id=:g"
    params: dict[str, Any] = {"offset": offset, "limit": limit}
    for name, value in (filters or {}).items():
        if value is None:
            continue
        column = master.filters.get(name, name)
        where += f" AND {column}=:{name}"
        params[name] = value
    with read() as connection:
        scoped = read_scope(connection, context, master.module)
        params.update(_scope(scoped))
        total = connection.execute(
            text(f"SELECT count(*) FROM {master.table} WHERE {where}"), params
        ).scalar_one()
        rows = connection.execute(
            text(
                f"SELECT {master.selection} FROM {master.table} WHERE {where} "
                f"ORDER BY {order}, id OFFSET :offset LIMIT :limit"
            ),
            params,
        ).mappings()
        return [present(row) for row in rows], total


def detail(master: Master, context: AuthContext, row_id: int) -> dict[str, Any]:
    with read() as connection:
        scoped = read_scope(connection, context, master.module)
        row = fetch(connection, master, scoped, row_id)
    if row is None:
        raise _not_found(master)
    return present(row)


def create(
    master: Master,
    context: AuthContext,
    values: dict[str, Any],
    key: str,
    *,
    check: Check | None = None,
) -> dict[str, Any]:
    def run(connection: Connection, scoped: AuthContext):
        reject_duplicate(connection, master, scoped, values, None)
        if check is not None:
            check(connection, scoped, dict(values), None, None)
        created = store(connection, master, scoped, values, None)
        return created, master.entity, created["id"]

    return action(
        master.module, context, f"{master.table}.create", key, values, run, 201
    )


def update(
    master: Master,
    context: AuthContext,
    row_id: int,
    values: dict[str, Any],
    key: str,
    *,
    check: Check | None = None,
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def run(connection: Connection, scoped: AuthContext):
        current = fetch(connection, master, scoped, row_id)
        if current is None:
            raise _not_found(master)
        merged = {**current, **values}
        reject_duplicate(connection, master, scoped, merged, row_id)
        if check is not None:
            check(connection, scoped, merged, current, row_id)
        return store(connection, master, scoped, values, row_id), master.entity, row_id

    return action(
        master.module,
        context,
        f"{master.table}.update",
        key,
        {"id": row_id, **values},
        run,
    )


def delete(master: Master, context: AuthContext, row_id: int, key: str) -> None:
    def run(connection: Connection, scoped: AuthContext):
        if fetch(connection, master, scoped, row_id) is None:
            raise _not_found(master)
        found = references(connection, master, scoped, row_id)
        if found:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                master.referenced_message,
                {"reason": "REFERENCED_BY_OTHERS", "references": found},
            )
        connection.execute(
            text(
                f"DELETE FROM {master.table} "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": row_id},
        )
        return {}, master.entity, row_id

    action(
        master.module,
        context,
        f"{master.table}.delete",
        key,
        {"id": row_id},
        run,
        204,
    )


def reject_duplicate(
    connection: Connection,
    master: Master,
    scoped: AuthContext,
    values: Mapping[str, Any],
    row_id: int | None,
) -> None:
    if duplicate(connection, master, scoped, values, row_id):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "입력값을 확인해 주세요.",
            {"fields": {master.duplicate_field: master.duplicate_message}},
        )
