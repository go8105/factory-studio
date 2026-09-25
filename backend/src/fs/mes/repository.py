"""MES 질의. 모든 질의는 S=(workspace_id, generation_id)를 조건에 포함한다.

기준정보(M-10~M-13)는 구조가 같아 표 하나의 명세(Master)로 조회·등록·수정·삭제를 공통 처리한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext

_S = "workspace_id=:w AND generation_id=:g"


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def row_dict(row: Any) -> dict[str, Any]:
    return {_camel(k): _value(v) for k, v in row.items()}


@dataclass(frozen=True)
class Master:
    table: str
    columns: str
    code: str
    # 코드가 유일한 범위(예: 공간 코드는 사업장 안에서 유일). None이면 S 전체.
    code_scope: str | None
    # 삭제를 막는 참조: (테이블, 컬럼, 표시명)
    references: tuple[tuple[str, str, str], ...]
    order: str


SITE = Master(
    "mes.site",
    "id,site_code,name,timezone,created_at",
    "site_code",
    None,
    (("mes.location", "site_id", "공간"),),
    "site_code, id",
)
LOCATION = Master(
    "mes.location",
    "id,site_id,parent_location_id,location_code,name,kind,created_at",
    "location_code",
    "site_id",
    (
        ("mes.location", "parent_location_id", "하위 공간"),
        ("mes.equipment", "location_id", "설비"),
    ),
    "site_id, location_code, id",
)
EQUIPMENT = Master(
    "mes.equipment",
    "id,location_id,equipment_code,name,equipment_type,is_active,created_at",
    "equipment_code",
    None,
    (
        ("mes.process_equipment", "equipment_id", "공정 허용 설비"),
        ("mes.operation_execution", "equipment_id", "공정 실행"),
    ),
    "equipment_code, id",
)
ITEM = Master(
    "mes.item",
    "id,item_code,name,base_unit,item_type,is_active,created_at",
    "item_code",
    None,
    (
        ("mes.item_unit_conversion", "item_id", "단위 환산"),
        ("mes.route_version", "item_id", "공정 경로"),
        ("mes.bom_version", "item_id", "BOM"),
        ("mes.bom_line", "material_item_id", "BOM 자재"),
        ("mes.production_plan_line", "item_id", "생산계획"),
        ("mes.work_order", "item_id", "작업지시"),
        ("mes.material_issue", "material_item_id", "자재 투입"),
    ),
    "item_code, id",
)
CONVERSION = Master(
    "mes.item_unit_conversion",
    "id,item_id,from_unit,to_unit,factor,created_at",
    "from_unit",
    "item_id",
    (),
    "item_id, from_unit, id",
)
PROCESS = Master(
    "mes.process",
    "id,process_code,name,process_type,is_active,created_at",
    "process_code",
    None,
    (("mes.route_step", "process_id", "공정 경로 단계"),),
    "process_code, id",
)
# ---- M-14 공정 경로 · M-15 BOM (버전: draft → published → retired) ----
ROUTE = Master(
    "mes.route_version",
    "id,item_id,route_code,version,status,published_at,retired_at,created_at",
    "route_code",
    None,
    (("mes.work_order", "route_version_id", "작업지시"),),
    "route_code, version, id",
)
STEP = Master(
    "mes.route_step",
    "id,route_version_id,process_id,sequence_no,created_at",
    "sequence_no",
    "route_version_id",
    (),
    "route_version_id, sequence_no, id",
)
BOM = Master(
    "mes.bom_version",
    "id,bom_code,item_id,version_no,status,published_at,created_at",
    "bom_code",
    None,
    (
        ("mes.work_order", "bom_version_id", "작업지시"),
        ("mes.material_issue", "bom_version_id", "자재 투입"),
    ),
    "item_id, version_no, id",
)
LINE = Master(
    "mes.bom_line",
    "id,bom_version_id,line_no,material_item_id,qty_per_unit,unit,loss_rate,created_at",
    "line_no",
    "bom_version_id",
    (),
    "bom_version_id, line_no, id",
)


def next_number(
    connection: Connection,
    context: AuthContext,
    table: str,
    column: str,
    key_column: str,
    key: Any,
) -> int:
    return connection.execute(
        text(
            f"SELECT coalesce(max({column}), 0) + 1 FROM {table} "
            f"WHERE {_S} AND {key_column}=:key"
        ),
        {**_s(context), "key": key},
    ).scalar_one()


def exists_where(
    connection: Connection, context: AuthContext, table: str, where: dict[str, Any]
) -> bool:
    condition = "".join(f" AND {column}=:{column}" for column in where)
    return (
        connection.execute(
            text(f"SELECT 1 FROM {table} WHERE {_S}{condition}"),
            {**_s(context), **where},
        ).first()
        is not None
    )


def replace_children(
    connection: Connection,
    context: AuthContext,
    table: str,
    parent_column: str,
    parent_id: int,
    rows: list[dict[str, Any]],
) -> None:
    connection.execute(
        text(f"DELETE FROM {table} WHERE {_S} AND {parent_column}=:p"),
        {**_s(context), "p": parent_id},
    )
    for row in rows:
        values = {parent_column: parent_id, **row}
        columns = ",".join(values)
        placeholders = ",".join(f":{column}" for column in values)
        connection.execute(
            text(
                f"INSERT INTO {table} (workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {placeholders})"
            ),
            {**_s(context), **values},
        )


def set_status(
    connection: Connection,
    context: AuthContext,
    master: Master,
    row_id: int,
    status: str,
    stamp: str | None,
) -> dict[str, Any]:
    stamp_sql = f", {stamp}=clock_timestamp()" if stamp else ""
    row = (
        connection.execute(
            text(
                f"UPDATE {master.table} SET status=:status{stamp_sql} "
                f"WHERE {_S} AND id=:id RETURNING {master.columns}"
            ),
            {**_s(context), "status": status, "id": row_id},
        )
        .mappings()
        .one()
    )
    return row_dict(row)


# 기준 단위를 참조하는 행(복합 FK (item_id, 단위) → item(id, base_unit)). 있으면 기준 단위를 바꿀 수 없다.
ITEM_UNIT_REFERENCES = (
    ("mes.item_unit_conversion", "item_id", "단위 환산"),
    ("mes.work_order", "item_id", "작업지시"),
)


def list_rows(
    connection: Connection,
    context: AuthContext,
    master: Master,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    where = _S + "".join(f" AND {column}=:{column}" for column in filters or {})
    rows = connection.execute(
        text(
            f"SELECT {master.columns} FROM {master.table} WHERE {where} "
            f"ORDER BY {master.order}"
        ),
        {**_s(context), **(filters or {})},
    ).mappings()
    return [row_dict(r) for r in rows]


def get_row(
    connection: Connection, context: AuthContext, master: Master, row_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {master.columns} FROM {master.table} WHERE {_S} AND id=:id"),
            {**_s(context), "id": row_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else row_dict(row)


def code_taken(
    connection: Connection,
    context: AuthContext,
    master: Master,
    code: str,
    scope_value: int | None,
    except_id: int | None,
) -> bool:
    scope = f" AND {master.code_scope}=:scope" if master.code_scope else ""
    return (
        connection.execute(
            text(
                f"SELECT 1 FROM {master.table} WHERE {_S}{scope} "
                f"AND {master.code}=:code AND id IS DISTINCT FROM :except"
            ),
            {**_s(context), "code": code, "scope": scope_value, "except": except_id},
        ).first()
        is not None
    )


def insert_row(
    connection: Connection, context: AuthContext, master: Master, values: dict[str, Any]
) -> dict[str, Any]:
    columns = ",".join(values)
    placeholders = ",".join(f":{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"INSERT INTO {master.table} (workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {placeholders}) RETURNING {master.columns}"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return row_dict(row)


def update_row(
    connection: Connection,
    context: AuthContext,
    master: Master,
    row_id: int,
    values: dict[str, Any],
) -> dict[str, Any]:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"UPDATE {master.table} SET {assignments} WHERE {_S} AND id=:id "
                f"RETURNING {master.columns}"
            ),
            {**_s(context), **values, "id": row_id},
        )
        .mappings()
        .one()
    )
    return row_dict(row)


def delete_row(
    connection: Connection, context: AuthContext, master: Master, row_id: int
) -> None:
    connection.execute(
        text(f"DELETE FROM {master.table} WHERE {_S} AND id=:id"),
        {**_s(context), "id": row_id},
    )


def count_references(
    connection: Connection,
    context: AuthContext,
    checks: tuple[tuple[str, str, str], ...],
    row_id: int,
) -> list[dict[str, Any]]:
    references = []
    for table, column, label in checks:
        count = connection.execute(
            text(f"SELECT count(*) FROM {table} WHERE {_S} AND {column}=:id"),
            {**_s(context), "id": row_id},
        ).scalar_one()
        if count:
            references.append({"table": table, "label": label, "count": count})
    return references


def location_ancestors(
    connection: Connection, context: AuthContext, location_id: int
) -> set[int]:
    """location_id 자신과 그 위 상위 공간들. 상위로 지정하려는 공간에 자신이 있으면 순환이다."""
    rows = connection.execute(
        text(
            "WITH RECURSIVE up(id, parent) AS ("
            " SELECT id, parent_location_id FROM mes.location"
            f" WHERE {_S} AND id=:id"
            " UNION"
            " SELECT l.id, l.parent_location_id FROM mes.location l"
            " JOIN up ON l.id=up.parent"
            " WHERE l.workspace_id=:w AND l.generation_id=:g"
            ") SELECT id FROM up"
        ),
        {**_s(context), "id": location_id},
    ).scalars()
    return set(rows)


def process_equipment_ids(
    connection: Connection, context: AuthContext
) -> dict[int, list[int]]:
    rows = connection.execute(
        text(
            f"SELECT process_id, equipment_id FROM mes.process_equipment WHERE {_S} "
            "ORDER BY process_id, equipment_id"
        ),
        _s(context),
    )
    result: dict[int, list[int]] = {}
    for process_id, equipment_id in rows:
        result.setdefault(process_id, []).append(equipment_id)
    return result


def replace_process_equipment(
    connection: Connection,
    context: AuthContext,
    process_id: int,
    equipment_ids: list[int],
) -> None:
    connection.execute(
        text(f"DELETE FROM mes.process_equipment WHERE {_S} AND process_id=:p"),
        {**_s(context), "p": process_id},
    )
    for equipment_id in equipment_ids:
        connection.execute(
            text(
                "INSERT INTO mes.process_equipment "
                "(workspace_id, generation_id, process_id, equipment_id) "
                "VALUES (:w, :g, :p, :e)"
            ),
            {**_s(context), "p": process_id, "e": equipment_id},
        )


def existing_ids(
    connection: Connection, context: AuthContext, table: str, ids: list[int]
) -> set[int]:
    return set(
        connection.execute(
            text(f"SELECT id FROM {table} WHERE {_S} AND id = ANY(:ids)"),
            {**_s(context), "ids": ids},
        ).scalars()
    )
