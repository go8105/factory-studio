"""QMS 업무 규칙 (FS-023 모듈 설계 3·5·6장).

- 검사 기준: 품목 코드별 버전. 게시 후 불변, 품목당 게시 1건(TX-Q1). 바꾸려면 개정(새 draft).
- 검사: 만들 때 게시 기준을 고정한다. 항목 판정은 서버가 계산하고, 한 항목이라도 FAIL이면 검사 FAIL.
  확정은 불변이며 FAIL 확정과 같은 트랜잭션에서 LOT 보류를 만든다(TX-Q2). 정정은 재검사.
- 보류: 재검사 합격 / 특채 / 폐기 판정으로만 해제한다(TX-Q3). MES 수량·패킹은 바꾸지 않는다(D10).
- MES 값은 fs.mes.interface로만 읽고 코드·수량 스냅샷으로 저장한다(D9·D11). MES를 꺼도 직접 입력으로 동작한다(D12).

잠금은 qms 행만 잡는다. 쓰기는 write_scope의 공간 잠금 뒤에 실행되므로 발번·게시 전환이 공간 안에서 직렬화된다.
업무 시각은 잠금을 얻은 뒤의 clock_timestamp()로 남긴다(FS-020g와 같은 이유).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import read_scope, write_scope
from fs.mes import interface as mes

MODULE = "qms"
_S = "workspace_id=:w AND generation_id=:g"


# ---------- 공통 ----------


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _read():
    engine = get_engine().execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    return engine.begin()


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row(row: Any) -> dict[str, Any]:
    return {_camel(k): _value(v) for k, v in row.items()}


def _field(field: str, message: str) -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {field: message}},
    )


def _fields(fields: dict[str, str]) -> ApiError:
    return ApiError(
        400, "VALIDATION_FAILED", "입력값을 확인해 주세요.", {"fields": fields}
    )


def _conflict(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


def _not_found(label: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{label}을(를) 찾을 수 없습니다.")


def _source_off() -> ApiError:
    return _conflict(
        "MES를 사용하지 않도록 설정했습니다. LOT 코드를 직접 입력해 검사할 수 있습니다.",
        "SOURCE_MODULE_DISABLED",
        sourceModule="mes",
    )


Action = Callable[[Connection, AuthContext], tuple[dict[str, Any], str, int]]


def _action(
    context: AuthContext,
    operation: str,
    key: str,
    body: Any,
    fn: Action,
    status: int = 200,
) -> dict[str, Any]:
    """쓰기 한 건: 공간 잠금 → 멱등 영수증 확인 → 처리 → 영수증 저장(같은 트랜잭션)."""
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        digest = request_digest(body)
        cached = find_receipt(connection, scoped, operation, key, digest)
        if cached is not None:
            return cached
        result, entity, entity_id = fn(connection, scoped)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            entity,
            entity_id,
            result,
            status,
        )
        return result


def _next_no(
    connection: Connection, scoped: AuthContext, table: str, column: str, prefix: str
) -> str:
    """QI-/QH-YYYYMMDD-NNN. 공간 잠금 안에서만 부른다."""
    stem = f"{prefix}-{business_today():%Y%m%d}-"
    used = connection.execute(
        text(f"SELECT count(*) FROM {table} WHERE {_S} AND {column} LIKE :stem"),
        {**_s(scoped), "stem": stem + "%"},
    ).scalar_one()
    return f"{stem}{used + 1:03d}"


def judge(
    method: str, lower: Any, upper: Any, measured: Any, passed: bool | None
) -> str | None:
    """항목 판정. 값이 없으면 None. RANGE는 한계를 포함한다(하한 ≤ 값 ≤ 상한, 한쪽만 있어도 된다)."""
    if method == "PASS_FAIL":
        return None if passed is None else ("PASS" if passed else "FAIL")
    if measured is None:
        return None
    value = Decimal(str(measured))
    if lower is not None and value < Decimal(str(lower)):
        return "FAIL"
    if upper is not None and value > Decimal(str(upper)):
        return "FAIL"
    return "PASS"


# ---------- 불량 유형 (Q-06) ----------

DEFECT_SQL = """
SELECT d.id, d.code, d.name, d.is_active, d.created_at,
       (SELECT count(*) FROM qms.inspection_value v
         WHERE v.workspace_id=d.workspace_id AND v.generation_id=d.generation_id
           AND v.defect_type_id=d.id) used_count
FROM qms.defect_type d WHERE d.workspace_id=:w AND d.generation_id=:g
"""


def _defect(
    connection: Connection, scoped: AuthContext, row_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(DEFECT_SQL + " AND d.id=:id"),
            {**_s(scoped), "id": row_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def list_defect_types(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = connection.execute(
            text(DEFECT_SQL + " ORDER BY d.code"), _s(scoped)
        ).mappings()
        return [_row(r) for r in rows]


def create_defect_type(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(connection: Connection, scoped: AuthContext):
        taken = connection.execute(
            text(f"SELECT 1 FROM qms.defect_type WHERE {_S} AND code=:code"),
            {**_s(scoped), "code": values["code"]},
        ).first()
        if taken:
            raise _field("code", "이미 사용 중인 코드입니다.")
        row_id = connection.execute(
            text(
                "INSERT INTO qms.defect_type(workspace_id,generation_id,code,name,is_active) "
                "VALUES (:w,:g,:code,:name,:active) RETURNING id"
            ),
            {
                **_s(scoped),
                "code": values["code"],
                "name": values["name"],
                "active": values["is_active"],
            },
        ).scalar_one()
        return _defect(connection, scoped, row_id), "defect_type", row_id

    return _action(context, "qms.defect_type.create", key, values, fn, 201)


def update_defect_type(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def fn(connection: Connection, scoped: AuthContext):
        if _defect(connection, scoped, row_id) is None:
            raise _not_found("불량 유형")
        sets = ", ".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE qms.defect_type SET {sets} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": row_id},
        )
        return _defect(connection, scoped, row_id), "defect_type", row_id

    return _action(context, f"qms.defect_type.update:{row_id}", key, values, fn)


def delete_defect_type(context: AuthContext, row_id: int, key: str) -> dict[str, Any]:
    def fn(connection: Connection, scoped: AuthContext):
        found = _defect(connection, scoped, row_id)
        if found is None:
            raise _not_found("불량 유형")
        if found["usedCount"]:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                "검사에 쓰인 불량 유형은 지울 수 없습니다. 사용 안 함으로 바꾸세요.",
                {"references": [{"label": "검사 측정값", "count": found["usedCount"]}]},
            )
        connection.execute(
            text(f"DELETE FROM qms.defect_type WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": row_id},
        )
        return {"id": row_id, "deleted": True}, "defect_type", row_id

    return _action(context, f"qms.defect_type.delete:{row_id}", key, {}, fn)


# ---------- 검사 기준 (Q-02) ----------

SPEC_SQL = """
SELECT s.id, s.item_code, s.item_name, s.version_no, s.status, s.published_at, s.note, s.created_at,
       (SELECT count(*) FROM qms.inspection_spec_item i
         WHERE i.workspace_id=s.workspace_id AND i.generation_id=s.generation_id AND i.spec_id=s.id) item_count,
       (SELECT count(*) FROM qms.inspection x
         WHERE x.workspace_id=s.workspace_id AND x.generation_id=s.generation_id AND x.spec_id=s.id) inspection_count
FROM qms.inspection_spec s WHERE s.workspace_id=:w AND s.generation_id=:g
"""
ITEM_SQL = f"""
SELECT id, spec_id, seq, name, method, lower_limit, upper_limit, unit, is_required
FROM qms.inspection_spec_item WHERE {_S} AND spec_id=:spec ORDER BY seq
"""


def _spec(
    connection: Connection, scoped: AuthContext, spec_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.inspection_spec WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": spec_id},
        )
    row = (
        connection.execute(
            text(SPEC_SQL + " AND s.id=:id"), {**_s(scoped), "id": spec_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    spec = _row(row)
    spec["items"] = [
        _row(r)
        for r in connection.execute(
            text(ITEM_SQL), {**_s(scoped), "spec": spec_id}
        ).mappings()
    ]
    return spec


def _spec_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """항목 형식 검사(DB CHECK와 같은 규칙을 먼저 화면용 필드 오류로 돌려준다)."""
    errors: dict[str, str] = {}
    for index, item in enumerate(items):
        lower, upper = item.get("lower_limit"), item.get("upper_limit")
        if item["method"] == "PASS_FAIL":
            if lower is not None or upper is not None or item.get("unit"):
                errors[f"items.{index}.method"] = (
                    "합·부 항목에는 한계·단위를 넣지 않습니다."
                )
        else:
            if lower is None and upper is None:
                errors[f"items.{index}.lowerLimit"] = (
                    "하한이나 상한 중 하나는 입력하세요."
                )
            if not item.get("unit"):
                errors[f"items.{index}.unit"] = "단위를 입력하세요."
            if (
                lower is not None
                and upper is not None
                and Decimal(lower) > Decimal(upper)
            ):
                errors[f"items.{index}.upperLimit"] = (
                    "상한은 하한보다 크거나 같아야 합니다."
                )
    if errors:
        raise _fields(errors)
    return items


def _insert_items(
    connection: Connection,
    scoped: AuthContext,
    spec_id: int,
    items: list[dict[str, Any]],
) -> None:
    for seq, item in enumerate(items, start=1):
        connection.execute(
            text(
                "INSERT INTO qms.inspection_spec_item"
                "(workspace_id,generation_id,spec_id,seq,name,method,lower_limit,upper_limit,unit,is_required) "
                "VALUES (:w,:g,:spec,:seq,:name,:method,:lower,:upper,:unit,:required)"
            ),
            {
                **_s(scoped),
                "spec": spec_id,
                "seq": seq,
                "name": item["name"],
                "method": item["method"],
                "lower": item.get("lower_limit"),
                "upper": item.get("upper_limit"),
                "unit": item.get("unit") if item["method"] == "RANGE" else None,
                "required": item.get("is_required", True),
            },
        )


def _draft_for_item(
    connection: Connection, scoped: AuthContext, item_code: str
) -> int | None:
    return connection.execute(
        text(
            f"SELECT id FROM qms.inspection_spec WHERE {_S} AND item_code=:item AND status='draft'"
        ),
        {**_s(scoped), "item": item_code},
    ).scalar()


def list_specs(
    context: AuthContext, item_code: str | None, status: str | None
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        sql, params = SPEC_SQL, dict(_s(scoped))
        if item_code:
            sql += " AND s.item_code=:item"
            params["item"] = item_code
        if status:
            sql += " AND s.status=:status"
            params["status"] = status
        rows = connection.execute(
            text(sql + " ORDER BY s.item_code, s.version_no DESC"), params
        ).mappings()
        return [_row(r) for r in rows]


def get_spec(context: AuthContext, spec_id: int) -> dict[str, Any]:
    with _read() as connection:
        found = _spec(connection, read_scope(connection, context, MODULE), spec_id)
    if found is None:
        raise _not_found("검사 기준")
    return found


def create_spec(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    items = _spec_items(values.get("items", []))

    def fn(connection: Connection, scoped: AuthContext):
        draft = _draft_for_item(connection, scoped, values["item_code"])
        if draft is not None:
            raise _conflict(
                "이 품목에는 작성 중인 기준이 있습니다.", "DRAFT_EXISTS", specId=draft
            )
        version = connection.execute(
            text(
                f"SELECT coalesce(max(version_no),0)+1 FROM qms.inspection_spec WHERE {_S} AND item_code=:item"
            ),
            {**_s(scoped), "item": values["item_code"]},
        ).scalar_one()
        spec_id = connection.execute(
            text(
                "INSERT INTO qms.inspection_spec(workspace_id,generation_id,item_code,item_name,version_no,note) "
                "VALUES (:w,:g,:item,:name,:version,:note) RETURNING id"
            ),
            {
                **_s(scoped),
                "item": values["item_code"],
                "name": values["item_name"],
                "version": version,
                "note": values.get("note"),
            },
        ).scalar_one()
        _insert_items(connection, scoped, spec_id, items)
        return _spec(connection, scoped, spec_id), "inspection_spec", spec_id

    return _action(context, "qms.spec.create", key, values, fn, 201)


def _draft_spec(
    connection: Connection, scoped: AuthContext, spec_id: int
) -> dict[str, Any]:
    spec = _spec(connection, scoped, spec_id, lock=True)
    if spec is None:
        raise _not_found("검사 기준")
    if spec["status"] != "draft":
        raise _conflict(
            "게시한 기준은 바꿀 수 없습니다. 개정해서 새 버전을 만드세요.",
            "PUBLISHED_IMMUTABLE",
        )
    return spec


def update_spec(
    context: AuthContext, spec_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    items = _spec_items(values["items"]) if values.get("items") is not None else None

    def fn(connection: Connection, scoped: AuthContext):
        _draft_spec(connection, scoped, spec_id)
        if "note" in values:
            connection.execute(
                text(
                    f"UPDATE qms.inspection_spec SET note=:note WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "note": values["note"], "id": spec_id},
            )
        if items is not None:
            connection.execute(
                text(
                    f"DELETE FROM qms.inspection_spec_item WHERE {_S} AND spec_id=:id"
                ),
                {**_s(scoped), "id": spec_id},
            )
            _insert_items(connection, scoped, spec_id, items)
        return _spec(connection, scoped, spec_id), "inspection_spec", spec_id

    return _action(context, f"qms.spec.update:{spec_id}", key, values, fn)


def delete_spec(context: AuthContext, spec_id: int, key: str) -> dict[str, Any]:
    def fn(connection: Connection, scoped: AuthContext):
        _draft_spec(connection, scoped, spec_id)
        for table, column in (
            ("qms.inspection_spec_item", "spec_id"),
            ("qms.inspection_spec", "id"),
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE {_S} AND {column}=:id"),
                {**_s(scoped), "id": spec_id},
            )
        return {"id": spec_id, "deleted": True}, "inspection_spec", spec_id

    return _action(context, f"qms.spec.delete:{spec_id}", key, {}, fn)


def publish_spec(context: AuthContext, spec_id: int, key: str) -> dict[str, Any]:
    """TX-Q1: 같은 품목의 기존 게시 버전을 retired로 바꾸고 이 버전을 게시한다."""

    def fn(connection: Connection, scoped: AuthContext):
        spec = _draft_spec(connection, scoped, spec_id)
        if not spec["items"]:
            raise _conflict(
                "검사 항목이 1개 이상 있어야 게시할 수 있습니다.", "NO_ITEMS"
            )
        connection.execute(
            text(
                f"SELECT 1 FROM qms.inspection_spec WHERE {_S} AND item_code=:item AND status='published' FOR UPDATE"
            ),
            {**_s(scoped), "item": spec["itemCode"]},
        )
        connection.execute(
            text(
                f"UPDATE qms.inspection_spec SET status='retired' WHERE {_S} AND item_code=:item AND status='published'"
            ),
            {**_s(scoped), "item": spec["itemCode"]},
        )
        connection.execute(
            text(
                f"UPDATE qms.inspection_spec SET status='published', published_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": spec_id},
        )
        return _spec(connection, scoped, spec_id), "inspection_spec", spec_id

    return _action(context, f"qms.spec.publish:{spec_id}", key, {}, fn)


def retire_spec(context: AuthContext, spec_id: int, key: str) -> dict[str, Any]:
    def fn(connection: Connection, scoped: AuthContext):
        spec = _spec(connection, scoped, spec_id, lock=True)
        if spec is None:
            raise _not_found("검사 기준")
        if spec["status"] != "published":
            raise _conflict("게시 중인 기준만 폐기할 수 있습니다.", "NOT_PUBLISHED")
        connection.execute(
            text(
                f"UPDATE qms.inspection_spec SET status='retired' WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": spec_id},
        )
        return _spec(connection, scoped, spec_id), "inspection_spec", spec_id

    return _action(context, f"qms.spec.retire:{spec_id}", key, {}, fn)


def revise_spec(context: AuthContext, spec_id: int, key: str) -> dict[str, Any]:
    """게시·폐기 버전을 복사해 새 draft(version + 1)를 만든다."""

    def fn(connection: Connection, scoped: AuthContext):
        spec = _spec(connection, scoped, spec_id)
        if spec is None:
            raise _not_found("검사 기준")
        if spec["status"] == "draft":
            raise _conflict("작성 중인 기준은 그대로 고치면 됩니다.", "ALREADY_DRAFT")
        draft = _draft_for_item(connection, scoped, spec["itemCode"])
        if draft is not None:
            raise _conflict(
                "이 품목에는 작성 중인 기준이 있습니다.", "DRAFT_EXISTS", specId=draft
            )
        version = connection.execute(
            text(
                f"SELECT max(version_no)+1 FROM qms.inspection_spec WHERE {_S} AND item_code=:item"
            ),
            {**_s(scoped), "item": spec["itemCode"]},
        ).scalar_one()
        new_id = connection.execute(
            text(
                "INSERT INTO qms.inspection_spec(workspace_id,generation_id,item_code,item_name,version_no,note) "
                "VALUES (:w,:g,:item,:name,:version,:note) RETURNING id"
            ),
            {
                **_s(scoped),
                "item": spec["itemCode"],
                "name": spec["itemName"],
                "version": version,
                "note": spec["note"],
            },
        ).scalar_one()
        _insert_items(
            connection,
            scoped,
            new_id,
            [
                {
                    "name": i["name"],
                    "method": i["method"],
                    "lower_limit": i["lowerLimit"],
                    "upper_limit": i["upperLimit"],
                    "unit": i["unit"],
                    "is_required": i["isRequired"],
                }
                for i in spec["items"]
            ],
        )
        return _spec(connection, scoped, new_id), "inspection_spec", new_id

    return _action(context, f"qms.spec.revise:{spec_id}", key, {}, fn, 201)


# ---------- MES 조회 (Q-03, D9) ----------


def mes_items(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        rows = mes.items(connection, read_scope(connection, context, MODULE))
    if rows is None:
        raise _source_off()
    return rows


def _published_items(connection: Connection, scoped: AuthContext) -> set[str]:
    return set(
        connection.execute(
            text(
                f"SELECT item_code FROM qms.inspection_spec WHERE {_S} AND status='published'"
            ),
            _s(scoped),
        ).scalars()
    )


def _lot_states(
    connection: Connection, scoped: AuthContext, lot_nos: list[str]
) -> dict[str, dict[str, Any]]:
    """LOT별 QMS 상태: 작성 중 검사 id, 마지막 확정 판정."""
    states: dict[str, dict[str, Any]] = {}
    rows = connection.execute(
        text(
            f"SELECT id, lot_no, status, result FROM qms.inspection WHERE {_S} AND lot_no = ANY(:lots) "
            "ORDER BY confirmed_at NULLS LAST, id"
        ),
        {**_s(scoped), "lots": lot_nos},
    ).mappings()
    for r in rows:
        state = states.setdefault(
            r["lot_no"], {"draftInspectionId": None, "latestResult": None}
        )
        if r["status"] == "draft":
            state["draftInspectionId"] = r["id"]
        else:
            state["latestResult"] = r["result"]
    return states


def mes_lots(context: AuthContext, pending: bool) -> list[dict[str, Any]]:
    """검사 대기(7.3): MES 완료 LOT 중 확정 검사가 없는 LOT. 계산 결과를 저장하지 않는다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        lots = mes.inspectable_lots(connection, scoped)
        if lots is None:
            raise _source_off()
        states = _lot_states(connection, scoped, [lot["lotNo"] for lot in lots])
        published = _published_items(connection, scoped)
    result = []
    for lot in lots:
        state = states.get(
            lot["lotNo"], {"draftInspectionId": None, "latestResult": None}
        )
        status = (
            "inspected"
            if state["latestResult"]
            else ("drafting" if state["draftInspectionId"] else "pending")
        )
        if pending and status == "inspected":
            continue
        result.append(
            {**lot, **state, "status": status, "hasSpec": lot["itemCode"] in published}
        )
    return result


# ---------- 검사 (Q-04) ----------

INSPECTION_SQL = """
SELECT i.id, i.inspection_no, i.source, i.lot_no, i.item_code, i.item_name, i.lot_qty, i.unit,
       i.sample_qty, i.spec_id, s.version_no spec_version, i.reinspection_of_id, i.status, i.result,
       i.inspected_on, i.inspection_month, i.confirmed_at, i.note, i.created_at
FROM qms.inspection i
JOIN qms.inspection_spec s ON s.workspace_id=i.workspace_id AND s.generation_id=i.generation_id AND s.id=i.spec_id
WHERE i.workspace_id=:w AND i.generation_id=:g
"""
VALUE_SQL = """
SELECT t.id spec_item_id, t.seq, t.name, t.method, t.lower_limit, t.upper_limit, t.unit, t.is_required,
       v.id value_id, v.measured_value, v.pass_value, v.judgement, v.defect_type_id, d.code defect_code, d.name defect_name
FROM qms.inspection_spec_item t
LEFT JOIN qms.inspection_value v ON v.workspace_id=t.workspace_id AND v.generation_id=t.generation_id
 AND v.spec_item_id=t.id AND v.inspection_id=:inspection
LEFT JOIN qms.defect_type d ON d.workspace_id=v.workspace_id AND d.generation_id=v.generation_id AND d.id=v.defect_type_id
WHERE t.workspace_id=:w AND t.generation_id=:g AND t.spec_id=:spec
ORDER BY t.seq
"""
HOLD_SQL = """
SELECT h.id, h.hold_no, h.lot_no, h.item_code, h.inspection_id, c.inspection_no, h.status, h.held_at,
       h.disposition, h.release_inspection_id, r.inspection_no release_inspection_no, h.release_reason,
       h.released_at, h.created_at
FROM qms.quality_hold h
JOIN qms.inspection c ON c.workspace_id=h.workspace_id AND c.generation_id=h.generation_id AND c.id=h.inspection_id
LEFT JOIN qms.inspection r ON r.workspace_id=h.workspace_id AND r.generation_id=h.generation_id
 AND r.id=h.release_inspection_id
WHERE h.workspace_id=:w AND h.generation_id=:g
"""


def _inspection(
    connection: Connection, scoped: AuthContext, inspection_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.inspection WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": inspection_id},
        )
    row = (
        connection.execute(
            text(INSPECTION_SQL + " AND i.id=:id"), {**_s(scoped), "id": inspection_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    found = _row(row)
    found["values"] = [
        _row(r)
        for r in connection.execute(
            text(VALUE_SQL),
            {**_s(scoped), "inspection": inspection_id, "spec": found["specId"]},
        ).mappings()
    ]
    hold = (
        connection.execute(
            text(HOLD_SQL + " AND h.lot_no=:lot AND h.status='held'"),
            {**_s(scoped), "lot": found["lotNo"]},
        )
        .mappings()
        .first()
    )
    found["activeHold"] = None if hold is None else _row(hold)
    return found


def _published_spec(connection: Connection, scoped: AuthContext, item_code: str) -> int:
    spec_id = connection.execute(
        text(
            f"SELECT id FROM qms.inspection_spec WHERE {_S} AND item_code=:item AND status='published'"
        ),
        {**_s(scoped), "item": item_code},
    ).scalar()
    if spec_id is None:
        raise _conflict(
            "이 품목에는 게시한 검사 기준이 없습니다. 검사 기준을 먼저 게시하세요.",
            "NO_PUBLISHED_SPEC",
            itemCode=item_code,
        )
    return spec_id


def _no_draft_for_lot(connection: Connection, scoped: AuthContext, lot_no: str) -> None:
    draft = connection.execute(
        text(
            f"SELECT id FROM qms.inspection WHERE {_S} AND lot_no=:lot AND status='draft'"
        ),
        {**_s(scoped), "lot": lot_no},
    ).scalar()
    if draft is not None:
        raise _conflict(
            "이 LOT에는 작성 중인 검사가 있습니다.", "DRAFT_EXISTS", inspectionId=draft
        )


def _insert_inspection(
    connection: Connection,
    scoped: AuthContext,
    snap: dict[str, Any],
    spec_id: int,
    reinspection_of: int | None,
) -> int:
    inspected_on = snap["inspected_on"]
    inspection_id = connection.execute(
        text(
            "INSERT INTO qms.inspection(workspace_id,generation_id,inspection_no,source,lot_no,item_code,item_name,"
            "lot_qty,unit,sample_qty,spec_id,reinspection_of_id,inspected_on,inspection_month,note) "
            "VALUES (:w,:g,:no,:source,:lot,:item,:name,:lot_qty,:unit,:sample,:spec,:again,:on,:month,:note) RETURNING id"
        ),
        {
            **_s(scoped),
            "no": _next_no(connection, scoped, "qms.inspection", "inspection_no", "QI"),
            "source": snap["source"],
            "lot": snap["lot_no"],
            "item": snap["item_code"],
            "name": snap["item_name"],
            "lot_qty": snap["lot_qty"],
            "unit": snap["unit"],
            "sample": snap["sample_qty"],
            "spec": spec_id,
            "again": reinspection_of,
            "on": inspected_on,
            "month": f"{inspected_on:%Y-%m}",
            "note": snap.get("note"),
        },
    ).scalar_one()
    # 항목마다 빈 측정값 행을 만들어 둔다. 수정은 행 단위 UPDATE로 한다.
    connection.execute(
        text(
            "INSERT INTO qms.inspection_value(workspace_id,generation_id,inspection_id,spec_item_id) "
            f"SELECT :w,:g,:inspection,id FROM qms.inspection_spec_item WHERE {_S} AND spec_id=:spec"
        ),
        {**_s(scoped), "inspection": inspection_id, "spec": spec_id},
    )
    return inspection_id


def _sample_ok(sample: Any, lot_qty: Any) -> None:
    if Decimal(str(sample)) <= 0:
        raise _field("sampleQty", "표본 수량은 0보다 커야 합니다.")
    if Decimal(str(sample)) > Decimal(str(lot_qty)):
        raise _field("sampleQty", "표본 수량은 LOT 수량 이하여야 합니다.")


def list_inspections(
    context: AuthContext,
    status: str | None,
    result: str | None,
    month: str | None,
    lot_no: str | None,
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        sql, params = INSPECTION_SQL, dict(_s(scoped))
        for column, value in (
            ("status", status),
            ("result", result),
            ("inspection_month", month),
            ("lot_no", lot_no),
        ):
            if value:
                sql += f" AND i.{column}=:{column}"
                params[column] = value
        rows = connection.execute(
            text(sql + " ORDER BY i.inspected_on DESC, i.id DESC"), params
        ).mappings()
        return [_row(r) for r in rows]


def get_inspection(context: AuthContext, inspection_id: int) -> dict[str, Any]:
    with _read() as connection:
        found = _inspection(
            connection, read_scope(connection, context, MODULE), inspection_id
        )
    if found is None:
        raise _not_found("검사")
    return found


def create_inspection(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    body = {k: (str(v) if isinstance(v, date) else v) for k, v in values.items()}

    def fn(connection: Connection, scoped: AuthContext):
        if values["source"] == "MES":
            snap = mes.lot_snapshot(connection, scoped, values["lot_no"])
            if snap is None:
                if not mes.enabled(connection, scoped):
                    raise _source_off()
                raise _conflict(
                    "검사할 수 있는 완료 LOT이 아닙니다.",
                    "LOT_NOT_INSPECTABLE",
                    lotNo=values["lot_no"],
                )
            fields = {
                "item_code": snap["itemCode"],
                "item_name": snap["itemName"],
                "lot_qty": snap["finalGoodQty"],
                "unit": snap["unit"],
            }
        else:
            missing = {
                _camel(k): "직접 입력 검사에는 필수입니다."
                for k in ("item_code", "item_name", "lot_qty", "unit")
                if not values.get(k)
            }
            if missing:
                raise _fields(missing)
            if Decimal(values["lot_qty"]) <= 0:
                raise _field("lotQty", "LOT 수량은 0보다 커야 합니다.")
            fields = {
                k: values[k] for k in ("item_code", "item_name", "lot_qty", "unit")
            }
        _sample_ok(values["sample_qty"], fields["lot_qty"])
        _no_draft_for_lot(connection, scoped, values["lot_no"])
        spec_id = _published_spec(connection, scoped, fields["item_code"])
        snap = {
            **fields,
            "source": values["source"],
            "lot_no": values["lot_no"],
            "sample_qty": values["sample_qty"],
            "inspected_on": values.get("inspected_on") or business_today(),
            "note": values.get("note"),
        }
        inspection_id = _insert_inspection(connection, scoped, snap, spec_id, None)
        return (
            _inspection(connection, scoped, inspection_id),
            "inspection",
            inspection_id,
        )

    return _action(context, "qms.inspection.create", key, body, fn, 201)


def _draft_inspection(
    connection: Connection, scoped: AuthContext, inspection_id: int
) -> dict[str, Any]:
    found = _inspection(connection, scoped, inspection_id, lock=True)
    if found is None:
        raise _not_found("검사")
    if found["status"] != "draft":
        raise _conflict(
            "확정한 검사는 바꿀 수 없습니다. 재검사하세요.", "CONFIRMED_IMMUTABLE"
        )
    return found


def update_inspection(
    context: AuthContext, inspection_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    body = {k: (str(v) if isinstance(v, date) else v) for k, v in values.items()}

    def fn(connection: Connection, scoped: AuthContext):
        found = _draft_inspection(connection, scoped, inspection_id)
        if values.get("sample_qty") is not None:
            _sample_ok(values["sample_qty"], found["lotQty"])
            connection.execute(
                text(f"UPDATE qms.inspection SET sample_qty=:v WHERE {_S} AND id=:id"),
                {**_s(scoped), "v": values["sample_qty"], "id": inspection_id},
            )
        if values.get("inspected_on") is not None:
            on = values["inspected_on"]
            connection.execute(
                text(
                    f"UPDATE qms.inspection SET inspected_on=:on, inspection_month=:month WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "on": on, "month": f"{on:%Y-%m}", "id": inspection_id},
            )
        if "note" in values:
            connection.execute(
                text(f"UPDATE qms.inspection SET note=:v WHERE {_S} AND id=:id"),
                {**_s(scoped), "v": values["note"], "id": inspection_id},
            )
        items = {v["specItemId"]: v for v in found["values"]}
        active_defects = set(
            connection.execute(
                text(f"SELECT id FROM qms.defect_type WHERE {_S} AND is_active"),
                _s(scoped),
            ).scalars()
        )
        errors: dict[str, str] = {}
        for entry in values.get("values") or []:
            item = items.get(entry["spec_item_id"])
            if item is None:
                errors[f"values.{entry['spec_item_id']}"] = (
                    "이 검사의 기준 항목이 아닙니다."
                )
                continue
            seq = item["seq"]
            if item["method"] == "RANGE" and entry.get("pass_value") is not None:
                errors[f"values.{seq}"] = "수치 항목에는 측정값을 입력하세요."
                continue
            if (
                item["method"] == "PASS_FAIL"
                and entry.get("measured_value") is not None
            ):
                errors[f"values.{seq}"] = "합·부 항목에는 합격·불합격을 고르세요."
                continue
            judgement = judge(
                item["method"],
                item["lowerLimit"],
                item["upperLimit"],
                entry.get("measured_value"),
                entry.get("pass_value"),
            )
            defect = entry.get("defect_type_id") if judgement == "FAIL" else None
            if defect is not None and defect not in active_defects:
                errors[f"values.{seq}.defectTypeId"] = "사용 중인 불량 유형을 고르세요."
                continue
            connection.execute(
                text(
                    "UPDATE qms.inspection_value SET measured_value=:m, pass_value=:p, judgement=:j, defect_type_id=:d "
                    f"WHERE {_S} AND inspection_id=:inspection AND spec_item_id=:item"
                ),
                {
                    **_s(scoped),
                    "m": entry.get("measured_value"),
                    "p": entry.get("pass_value"),
                    "j": judgement,
                    "d": defect,
                    "inspection": inspection_id,
                    "item": entry["spec_item_id"],
                },
            )
        if errors:
            raise _fields(errors)
        return (
            _inspection(connection, scoped, inspection_id),
            "inspection",
            inspection_id,
        )

    return _action(context, f"qms.inspection.update:{inspection_id}", key, body, fn)


def confirm_inspection(
    context: AuthContext, inspection_id: int, key: str
) -> dict[str, Any]:
    """TX-Q2: 판정 → 확정 → FAIL이면 LOT 보류(활성 보류가 있으면 그대로 둔다)."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _draft_inspection(connection, scoped, inspection_id)
        errors: dict[str, str] = {}
        for v in found["values"]:
            if v["isRequired"] and v["judgement"] is None:
                errors[f"values.{v['seq']}"] = "값을 입력하세요."
            if v["judgement"] == "FAIL" and v["defectTypeId"] is None:
                errors[f"values.{v['seq']}.defectTypeId"] = (
                    "불합격 항목의 불량 유형을 고르세요."
                )
        if errors:
            raise _fields(errors)
        result = (
            "FAIL" if any(v["judgement"] == "FAIL" for v in found["values"]) else "PASS"
        )
        connection.execute(
            text(
                f"UPDATE qms.inspection SET status='confirmed', result=:r, confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "r": result, "id": inspection_id},
        )
        if result == "FAIL":
            # 같은 LOT 불합격이 동시에 확정돼도 활성 보류는 부분 유니크로 1건만 남는다(AC-103).
            connection.execute(
                text(
                    "INSERT INTO qms.quality_hold(workspace_id,generation_id,hold_no,lot_no,item_code,inspection_id,held_at) "
                    "VALUES (:w,:g,:no,:lot,:item,:inspection,clock_timestamp()) "
                    "ON CONFLICT (workspace_id,generation_id,lot_no) WHERE status='held' DO NOTHING"
                ),
                {
                    **_s(scoped),
                    "no": _next_no(
                        connection, scoped, "qms.quality_hold", "hold_no", "QH"
                    ),
                    "lot": found["lotNo"],
                    "item": found["itemCode"],
                    "inspection": inspection_id,
                },
            )
        return (
            _inspection(connection, scoped, inspection_id),
            "inspection",
            inspection_id,
        )

    return _action(context, f"qms.inspection.confirm:{inspection_id}", key, {}, fn)


def reinspect(context: AuthContext, inspection_id: int, key: str) -> dict[str, Any]:
    """같은 LOT의 새 draft. 현재 게시 기준을 쓰고 원 검사를 가리킨다."""

    def fn(connection: Connection, scoped: AuthContext):
        original = _inspection(connection, scoped, inspection_id)
        if original is None:
            raise _not_found("검사")
        if original["status"] != "confirmed":
            raise _conflict("확정한 검사만 재검사할 수 있습니다.", "NOT_CONFIRMED")
        _no_draft_for_lot(connection, scoped, original["lotNo"])
        spec_id = _published_spec(connection, scoped, original["itemCode"])
        snap = {
            "source": original["source"],
            "lot_no": original["lotNo"],
            "item_code": original["itemCode"],
            "item_name": original["itemName"],
            "lot_qty": original["lotQty"],
            "unit": original["unit"],
            "sample_qty": original["sampleQty"],
            "inspected_on": business_today(),
        }
        new_id = _insert_inspection(connection, scoped, snap, spec_id, inspection_id)
        return _inspection(connection, scoped, new_id), "inspection", new_id

    return _action(
        context, f"qms.inspection.reinspect:{inspection_id}", key, {}, fn, 201
    )


def delete_inspection(
    context: AuthContext, inspection_id: int, key: str
) -> dict[str, Any]:
    def fn(connection: Connection, scoped: AuthContext):
        _draft_inspection(connection, scoped, inspection_id)
        for table, column in (
            ("qms.inspection_value", "inspection_id"),
            ("qms.inspection", "id"),
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE {_S} AND {column}=:id"),
                {**_s(scoped), "id": inspection_id},
            )
        return {"id": inspection_id, "deleted": True}, "inspection", inspection_id

    return _action(context, f"qms.inspection.delete:{inspection_id}", key, {}, fn)


# ---------- 품질 보류 (Q-05) ----------


def _hold(
    connection: Connection, scoped: AuthContext, hold_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.quality_hold WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": hold_id},
        )
    row = (
        connection.execute(
            text(HOLD_SQL + " AND h.id=:id"), {**_s(scoped), "id": hold_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    hold = _row(row)
    # 해제 후보: 보류 이후 확정된 같은 LOT의 검사(재검사 합격이면 REINSPECTED로 풀 수 있다).
    hold["reinspections"] = [
        _row(r)
        for r in connection.execute(
            text(
                INSPECTION_SQL
                + " AND i.lot_no=:lot AND i.id<>:cause AND i.status='confirmed' AND i.confirmed_at > :held "
                "ORDER BY i.confirmed_at"
            ),
            {
                **_s(scoped),
                "lot": hold["lotNo"],
                "cause": hold["inspectionId"],
                "held": row["held_at"],
            },
        ).mappings()
    ]
    hold["failedItems"] = [
        _row(r)
        for r in connection.execute(
            text(
                "SELECT t.seq, t.name, v.measured_value, v.pass_value, t.lower_limit, t.upper_limit, t.unit, "
                "d.code defect_code, d.name defect_name FROM qms.inspection_value v "
                "JOIN qms.inspection_spec_item t ON t.workspace_id=v.workspace_id AND t.generation_id=v.generation_id "
                " AND t.id=v.spec_item_id "
                "LEFT JOIN qms.defect_type d ON d.workspace_id=v.workspace_id AND d.generation_id=v.generation_id "
                " AND d.id=v.defect_type_id "
                "WHERE v.workspace_id=:w AND v.generation_id=:g AND v.inspection_id=:cause AND v.judgement='FAIL' "
                "ORDER BY t.seq"
            ),
            {**_s(scoped), "cause": hold["inspectionId"]},
        ).mappings()
    ]
    return hold


def list_holds(context: AuthContext, status: str | None) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        sql, params = HOLD_SQL, dict(_s(scoped))
        if status:
            sql += " AND h.status=:status"
            params["status"] = status
        rows = connection.execute(
            text(sql + " ORDER BY h.held_at DESC, h.id DESC"), params
        ).mappings()
        return [_row(r) for r in rows]


def get_hold(context: AuthContext, hold_id: int) -> dict[str, Any]:
    with _read() as connection:
        found = _hold(connection, read_scope(connection, context, MODULE), hold_id)
    if found is None:
        raise _not_found("품질 보류")
    return found


def release_hold(
    context: AuthContext, hold_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """TX-Q3: 처분 조건을 확인하고 released로 바꾼다. MES 수량은 바꾸지 않는다(D10)."""
    disposition = values["disposition"]
    reason = (values.get("reason") or "").strip() or None
    if disposition in ("CONCESSION", "SCRAP") and reason is None:
        raise _field("reason", "특채·폐기 판정은 사유를 입력하세요.")
    if disposition == "REINSPECTED" and values.get("release_inspection_id") is None:
        raise _field("releaseInspectionId", "합격한 재검사를 고르세요.")

    def fn(connection: Connection, scoped: AuthContext):
        hold = _hold(connection, scoped, hold_id, lock=True)
        if hold is None:
            raise _not_found("품질 보류")
        if hold["status"] != "held":
            raise _conflict("이미 해제한 보류입니다.", "ALREADY_RELEASED")
        release_id = None
        if disposition == "REINSPECTED":
            release_id = values["release_inspection_id"]
            ok = next(
                (
                    i
                    for i in hold["reinspections"]
                    if i["id"] == release_id and i["result"] == "PASS"
                ),
                None,
            )
            if ok is None:
                raise _conflict(
                    "보류 이후 확정된 같은 LOT의 합격 재검사가 있어야 풀 수 있습니다.",
                    "RELEASE_NOT_ALLOWED",
                )
        connection.execute(
            text(
                "UPDATE qms.quality_hold SET status='released', disposition=:d, release_inspection_id=:r, "
                f"release_reason=:reason, released_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {
                **_s(scoped),
                "d": disposition,
                "r": release_id,
                "reason": reason,
                "id": hold_id,
            },
        )
        return _hold(connection, scoped, hold_id), "quality_hold", hold_id

    return _action(context, f"qms.hold.release:{hold_id}", key, values, fn)


# ---------- 대시보드 (Q-01) ----------


def dashboard(context: AuthContext, month: str | None) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if not month:
            # 서버가 정한 최근 월: 확정 검사가 있는 마지막 월, 없으면 업무 기준일의 월(F-01과 같은 방식).
            month = (
                connection.execute(
                    text(
                        f"SELECT max(inspection_month) FROM qms.inspection WHERE {_S} AND status='confirmed'"
                    ),
                    _s(scoped),
                ).scalar()
                or f"{business_today():%Y-%m}"
            )
        params = {**_s(scoped), "month": month}
        counts = (
            connection.execute(
                text(
                    f"SELECT count(*) total, count(*) FILTER (WHERE result='PASS') passed "
                    f"FROM qms.inspection WHERE {_S} AND status='confirmed' AND inspection_month=:month"
                ),
                params,
            )
            .mappings()
            .one()
        )
        daily = [
            _row(r)
            for r in connection.execute(
                text(
                    f"SELECT inspected_on date, count(*) inspected, count(*) FILTER (WHERE result='FAIL') failed "
                    f"FROM qms.inspection WHERE {_S} AND status='confirmed' AND inspection_month=:month "
                    "GROUP BY inspected_on ORDER BY inspected_on"
                ),
                params,
            ).mappings()
        ]
        defects = [
            _row(r)
            for r in connection.execute(
                text(
                    "SELECT d.code, d.name, count(*) count FROM qms.inspection_value v "
                    "JOIN qms.inspection i ON i.workspace_id=v.workspace_id AND i.generation_id=v.generation_id "
                    " AND i.id=v.inspection_id "
                    "JOIN qms.defect_type d ON d.workspace_id=v.workspace_id AND d.generation_id=v.generation_id "
                    " AND d.id=v.defect_type_id "
                    "WHERE v.workspace_id=:w AND v.generation_id=:g AND v.judgement='FAIL' "
                    " AND i.status='confirmed' AND i.inspection_month=:month "
                    "GROUP BY d.code, d.name ORDER BY count(*) DESC, d.code LIMIT 5"
                ),
                params,
            ).mappings()
        ]
        recent = [
            _row(r)
            for r in connection.execute(
                text(
                    INSPECTION_SQL
                    + " AND i.status='confirmed' AND i.result='FAIL' ORDER BY i.confirmed_at DESC LIMIT 5"
                ),
                _s(scoped),
            ).mappings()
        ]
        holds = [
            _row(r)
            for r in connection.execute(
                text(HOLD_SQL + " AND h.status='held' ORDER BY h.held_at DESC"),
                _s(scoped),
            ).mappings()
        ]
        lots = mes.inspectable_lots(connection, scoped)
        pending = None
        if lots is not None:
            states = _lot_states(connection, scoped, [lot["lotNo"] for lot in lots])
            pending = sum(
                1
                for lot in lots
                if not states.get(lot["lotNo"], {}).get("latestResult")
            )
    total, passed = counts["total"], counts["passed"]
    return {
        "month": month,
        "inspected": total,
        "passRate": None
        if total == 0
        else f"{Decimal(passed) * 100 / Decimal(total):.1f}",
        "activeHolds": len(holds),
        "pendingLots": pending,
        "daily": daily,
        "topDefects": defects,
        "recentFails": recent,
        "holds": holds,
    }
