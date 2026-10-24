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
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
from typing import Any

from sqlalchemy import Connection, text

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.erp import interface as erp
from fs.mes import interface as mes
from fs.spc import interface as spc

MODULE = "qms"
_S = "workspace_id=:w AND generation_id=:g"


# ---------- 공통 ----------


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


# 공통 엔진: 조회 트랜잭션(REPEATABLE READ · 읽기 전용)
_read = read


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


# 공통 엔진(fs.common.engine.action): 공간 잠금 → 멱등 영수증 → 처리 → 영수증 저장
_action = partial(action, MODULE)


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
        # SPC 미조치 이상은 배지로만 보인다(FS-028 D44). SPC를 끄면 null.
        signals = spc.open_signal_lot_nos(
            connection, scoped, [lot["lotNo"] for lot in lots]
        )
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
            {
                **lot,
                **state,
                "status": status,
                "hasSpec": lot["itemCode"] in published,
                "spcSignal": None if signals is None else lot["lotNo"] in signals,
            }
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
    kind: str = "OUTGOING",
    source_ref: str | None = None,
) -> int:
    inspected_on = snap["inspected_on"]
    inspection_id = connection.execute(
        text(
            "INSERT INTO qms.inspection(workspace_id,generation_id,inspection_no,source,lot_no,item_code,item_name,"
            "lot_qty,unit,sample_qty,spec_id,reinspection_of_id,inspected_on,inspection_month,note,"
            "inspection_kind,source_ref) "
            "VALUES (:w,:g,:no,:source,:lot,:item,:name,:lot_qty,:unit,:sample,:spec,:again,:on,:month,:note,"
            ":kind,:ref) RETURNING id"
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
            "kind": kind,
            "ref": source_ref,
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
        rows = [
            _row(r)
            for r in connection.execute(
                text(sql + " ORDER BY i.inspected_on DESC, i.id DESC"), params
            ).mappings()
        ]
        signals = spc.open_signal_lot_nos(
            connection, scoped, sorted({r["lotNo"] for r in rows})
        )
        for r in rows:
            r["spcSignal"] = None if signals is None else r["lotNo"] in signals
        return rows


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


# ---------- 계측기·교정 (Q-11, DSN-14 F61·F62) ----------

GAUGE = master.Master(
    module=MODULE,
    table="qms.gauge",
    columns=(
        "code",
        "name",
        "gauge_kind",
        "measure_range",
        "resolution",
        "calibration_cycle_days",
        "status",
    ),
    sort={"code": "code", "name": "name", "status": "status"},
    default_sort="code ASC",
    unique=("code",),
    filters={"status": "status"},
    references=(
        master.Reference("qms.inspection_value", "gauge_id", "검사 사용 기록"),
    ),
    not_found="계측기를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 사용 중인 계측기 번호입니다.",
    referenced_message=(
        "검사에 사용한 기록이 있어 삭제할 수 없습니다. 폐기로 바꿔 주세요."
    ),
)

# 교정 도래 경고는 30일 전부터(DSN-14 Q6). 차단이 아니라 표시다.
DUE_SOON_DAYS = 30

CALIBRATION_SQL = """
SELECT c.id, c.gauge_id, c.calibrated_on, c.next_due_on, c.result, c.agency,
       c.certificate_no, c.created_at
FROM qms.calibration c WHERE c.workspace_id=:w AND c.generation_id=:g
"""


def _due_state(next_due: date | None, today: date) -> str:
    """교정 상태: 기록 없음 / 기한 경과 / 임박 / 정상."""
    if next_due is None:
        return "NONE"
    if next_due < today:
        return "OVERDUE"
    return "SOON" if (next_due - today).days <= DUE_SOON_DAYS else "OK"


def _calibration_state(
    connection: Connection, scoped: AuthContext, gauge_ids: list[int]
) -> dict[int, dict[str, Any]]:
    """계측기별 **마지막 교정**. 도래는 저장하지 않고 여기서 파생한다(설계 노트)."""
    if not gauge_ids:
        return {}
    today = business_today()
    rows = connection.execute(
        text(
            "SELECT DISTINCT ON (gauge_id) gauge_id, calibrated_on, next_due_on, result "
            f"FROM qms.calibration WHERE {_S} AND gauge_id = ANY(:ids) "
            "ORDER BY gauge_id, calibrated_on DESC, id DESC"
        ),
        {**_s(scoped), "ids": gauge_ids},
    ).mappings()
    found = {
        r["gauge_id"]: {
            "lastCalibratedOn": r["calibrated_on"].isoformat(),
            "nextDueOn": r["next_due_on"].isoformat(),
            "lastResult": r["result"],
            "dueState": _due_state(r["next_due_on"], today),
            "dueInDays": (r["next_due_on"] - today).days,
        }
        for r in rows
    }
    blank = {
        "lastCalibratedOn": None,
        "nextDueOn": None,
        "lastResult": None,
        "dueState": "NONE",
        "dueInDays": None,
    }
    return {gauge_id: found.get(gauge_id, blank) for gauge_id in gauge_ids}


def gauges(context: AuthContext, **kwargs) -> tuple[list[dict[str, Any]], int]:
    """계측기 목록에 마지막 교정과 도래 상태를 얹는다."""
    rows, total = master.listing(GAUGE, context, **kwargs)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        state = _calibration_state(connection, scoped, [r["id"] for r in rows])
    return [{**r, **state[r["id"]]} for r in rows], total


def gauge(context: AuthContext, gauge_id: int) -> dict[str, Any]:
    found = master.detail(GAUGE, context, gauge_id)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        state = _calibration_state(connection, scoped, [gauge_id])[gauge_id]
        history = [
            _row(r)
            for r in connection.execute(
                text(
                    CALIBRATION_SQL
                    + " AND c.gauge_id=:id ORDER BY c.calibrated_on DESC, c.id DESC"
                ),
                {**_s(scoped), "id": gauge_id},
            ).mappings()
        ]
    return {**found, **state, "calibrations": history}


def create_gauge(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(GAUGE, context, values, key)


def update_gauge(context: AuthContext, gauge_id: int, values: dict, key: str):
    return master.update(GAUGE, context, gauge_id, values, key)


def delete_gauge(context: AuthContext, gauge_id: int, key: str) -> None:
    master.delete(GAUGE, context, gauge_id, key)


def add_calibration(
    context: AuthContext, gauge_id: int, values: dict[str, Any], key: str
):
    """교정 이력 1건. **불합격이면 계측기를 수리 중으로, 수리 중이 합격하면 사용 중으로** 돌린다(F62)."""

    def fn(connection: Connection, scoped: AuthContext):
        found = (
            connection.execute(
                text(
                    f"SELECT id, code, status, calibration_cycle_days FROM qms.gauge WHERE {_S} AND id=:id FOR UPDATE"
                ),
                {**_s(scoped), "id": gauge_id},
            )
            .mappings()
            .first()
        )
        if found is None:
            raise _not_found("계측기")
        if found["status"] == "RETIRED":
            raise _conflict(
                "폐기한 계측기에는 교정을 기록할 수 없습니다.", "GAUGE_RETIRED"
            )
        calibrated_on = values["calibrated_on"]
        if calibrated_on > business_today():
            raise _field("calibratedOn", "교정일은 오늘 이후일 수 없습니다.")
        # 기한을 적지 않으면 교정 주기로 정한다. 기관 성적서의 기한이 다르면 직접 적는다.
        next_due = values.get("next_due_on") or calibrated_on + timedelta(
            days=found["calibration_cycle_days"]
        )
        if next_due <= calibrated_on:
            raise _field("nextDueOn", "다음 기한은 교정일보다 뒤여야 합니다.")
        if connection.execute(
            text(
                f"SELECT 1 FROM qms.calibration WHERE {_S} AND gauge_id=:id AND calibrated_on=:on"
            ),
            {**_s(scoped), "id": gauge_id, "on": calibrated_on},
        ).first():
            raise _field("calibratedOn", "같은 날짜의 교정 기록이 이미 있습니다.")
        row = (
            connection.execute(
                text(
                    "INSERT INTO qms.calibration(workspace_id,generation_id,gauge_id,calibrated_on,"
                    "next_due_on,result,agency,certificate_no) "
                    "VALUES (:w,:g,:id,:on,:due,:result,:agency,:cert) "
                    "RETURNING id, gauge_id, calibrated_on, next_due_on, result, agency, certificate_no, created_at"
                ),
                {
                    **_s(scoped),
                    "id": gauge_id,
                    "on": calibrated_on,
                    "due": next_due,
                    "result": values["result"],
                    "agency": values.get("agency"),
                    "cert": values.get("certificate_no"),
                },
            )
            .mappings()
            .one()
        )
        status = (
            "REPAIR"
            if values["result"] == "FAIL"
            else ("ACTIVE" if found["status"] == "REPAIR" else found["status"])
        )
        if status != found["status"]:
            connection.execute(
                text(f"UPDATE qms.gauge SET status=:s WHERE {_S} AND id=:id"),
                {**_s(scoped), "s": status, "id": gauge_id},
            )
        return {**_row(row), "gaugeStatus": status}, "calibration", row["id"]

    return _action(
        context, "qms.calibration.create", key, {"id": gauge_id, **values}, fn, 201
    )


# ---------- 4M 변경 (Q-12, DSN-14 F06) ----------

CHANGE_SQL = """
SELECT n.id, n.cn_no, n.change_type, n.item_code, n.description, n.requested_on,
       n.effective_on, n.status, n.decided_at, n.decision_note,
       n.first_article_inspection_id, f.inspection_no first_article_no, f.result first_article_result,
       n.plm_eco_no, n.created_at
FROM qms.change_notice n
LEFT JOIN qms.inspection f ON f.workspace_id=n.workspace_id AND f.generation_id=n.generation_id
 AND f.id=n.first_article_inspection_id
WHERE n.workspace_id=:w AND n.generation_id=:g
"""


def _change(
    connection: Connection, scoped: AuthContext, cn_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.change_notice WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": cn_id},
        )
    row = (
        connection.execute(
            text(CHANGE_SQL + " AND n.id=:id"), {**_s(scoped), "id": cn_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def _first_articles(
    connection: Connection, scoped: AuthContext, cn_no: str
) -> list[dict[str, Any]]:
    """이 신고 번호를 원천으로 만든 초품 검사. 확정 합격 1건이면 확인 완료로 닫을 수 있다."""
    return [
        _row(r)
        for r in connection.execute(
            text(
                INSPECTION_SQL
                + " AND i.inspection_kind='FIRST_ARTICLE' AND i.source_ref=:ref"
                " ORDER BY i.id DESC"
            ),
            {**_s(scoped), "ref": cn_no},
        ).mappings()
    ]


def list_change_notices(
    context: AuthContext, status: str | None, change_type: str | None
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(
                    CHANGE_SQL
                    + " AND (CAST(:status AS text) IS NULL OR n.status=:status)"
                    " AND (CAST(:kind AS text) IS NULL OR n.change_type=:kind)"
                    " ORDER BY n.requested_on DESC, n.id DESC"
                ),
                {**_s(scoped), "status": status, "kind": change_type},
            ).mappings()
        ]


def get_change_notice(context: AuthContext, cn_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _change(connection, scoped, cn_id)
        if found is None:
            raise _not_found("4M 변경 신고")
        return {
            **found,
            "firstArticles": _first_articles(connection, scoped, found["cnNo"]),
        }


def create_change_notice(context: AuthContext, values: dict[str, Any], key: str):
    def fn(connection: Connection, scoped: AuthContext):
        requested_on = values.get("requested_on") or business_today()
        if values["effective_on"] < requested_on:
            raise _field("effectiveOn", "적용 예정일은 신청일 이후여야 합니다.")
        cn_id = connection.execute(
            text(
                "INSERT INTO qms.change_notice(workspace_id,generation_id,cn_no,change_type,"
                "item_code,description,requested_on,effective_on) "
                "VALUES (:w,:g,:no,:kind,:item,:desc,:on,:eff) RETURNING id"
            ),
            {
                **_s(scoped),
                "no": _next_no(connection, scoped, "qms.change_notice", "cn_no", "CN"),
                "kind": values["change_type"],
                "item": values["item_code"],
                "desc": values["description"],
                "on": requested_on,
                "eff": values["effective_on"],
            },
        ).scalar_one()
        return _change(connection, scoped, cn_id), "change_notice", cn_id

    return _action(context, "qms.change_notice.create", key, values, fn, 201)


def update_change_notice(context: AuthContext, cn_id: int, values: dict, key: str):
    """신청 중일 때만 고친다. 승인·반려 뒤에는 기록을 바꾸지 않는다."""
    if not values:
        raise _fields({"description": "변경할 항목이 없습니다."})

    def fn(connection: Connection, scoped: AuthContext):
        found = _change(connection, scoped, cn_id, lock=True)
        if found is None:
            raise _not_found("4M 변경 신고")
        if found["status"] != "REQUESTED":
            raise _conflict(
                "결정한 신고는 고칠 수 없습니다.",
                "NOT_REQUESTED",
                status=found["status"],
            )
        merged = {
            "requested_on": date.fromisoformat(found["requestedOn"]),
            "effective_on": date.fromisoformat(found["effectiveOn"]),
            **values,
        }
        if merged["effective_on"] < merged["requested_on"]:
            raise _field("effectiveOn", "적용 예정일은 신청일 이후여야 합니다.")
        assignments = ",".join(f"{name}=:{name}" for name in values)
        connection.execute(
            text(f"UPDATE qms.change_notice SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": cn_id},
        )
        return _change(connection, scoped, cn_id), "change_notice", cn_id

    return _action(
        context, "qms.change_notice.update", key, {"id": cn_id, **values}, fn
    )


def decide_change_notice(
    context: AuthContext, cn_id: int, values: dict[str, Any], key: str
):
    """승인 또는 반려. 신청 중일 때만 결정하고, 반려에는 의견을 받는다."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _change(connection, scoped, cn_id, lock=True)
        if found is None:
            raise _not_found("4M 변경 신고")
        if found["status"] != "REQUESTED":
            raise _conflict(
                "이미 결정한 신고입니다.", "ALREADY_DECIDED", status=found["status"]
            )
        status = "APPROVED" if values["approve"] else "REJECTED"
        note = (values.get("note") or "").strip()
        if status == "REJECTED" and not note:
            raise _field("note", "반려 의견을 적어 주세요.")
        connection.execute(
            text(
                f"UPDATE qms.change_notice SET status=:s, decided_at=clock_timestamp(), "
                f"decision_note=:note WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "s": status, "note": note or None, "id": cn_id},
        )
        return _change(connection, scoped, cn_id), "change_notice", cn_id

    return _action(
        context, "qms.change_notice.decide", key, {"id": cn_id, **values}, fn
    )


def create_first_article(
    context: AuthContext, cn_id: int, values: dict[str, Any], key: str
):
    """승인된 신고의 초품 검사를 만든다. 원천은 신고 번호이고 검사 기준은 품목의 게시본이다."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _change(connection, scoped, cn_id, lock=True)
        if found is None:
            raise _not_found("4M 변경 신고")
        if found["status"] != "APPROVED":
            raise _conflict(
                "승인한 신고에만 초품 검사를 만들 수 있습니다.",
                "NOT_APPROVED",
                status=found["status"],
            )
        spec_id = _published_spec(connection, scoped, found["itemCode"])
        item_name = connection.execute(
            text(f"SELECT item_name FROM qms.inspection_spec WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": spec_id},
        ).scalar_one()
        _no_draft_for_lot(connection, scoped, values["lot_no"])
        _sample_ok(values["sample_qty"], values["lot_qty"])
        inspection_id = _insert_inspection(
            connection,
            scoped,
            {
                "source": "QMS",
                "lot_no": values["lot_no"],
                "item_code": found["itemCode"],
                "item_name": item_name,
                "lot_qty": values["lot_qty"],
                "unit": values["unit"],
                "sample_qty": values["sample_qty"],
                "inspected_on": values.get("inspected_on") or business_today(),
                "note": values.get("note"),
            },
            spec_id,
            None,
            kind="FIRST_ARTICLE",
            source_ref=found["cnNo"],
        )
        return (
            _inspection(connection, scoped, inspection_id),
            "inspection",
            inspection_id,
        )

    return _action(
        context,
        "qms.change_notice.first_article",
        key,
        {"id": cn_id, **values},
        fn,
        201,
    )


def verify_change_notice(context: AuthContext, cn_id: int, values: dict, key: str):
    """초품 검사 합격으로 확인 완료. 불합격이면 승인 상태 그대로 두고 다시 검사한다(DB_POLICY)."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _change(connection, scoped, cn_id, lock=True)
        if found is None:
            raise _not_found("4M 변경 신고")
        if found["status"] != "APPROVED":
            raise _conflict(
                "승인한 신고만 확인 완료할 수 있습니다.",
                "NOT_APPROVED",
                status=found["status"],
            )
        inspection_id = values["first_article_inspection_id"]
        passed = {
            i["id"]
            for i in _first_articles(connection, scoped, found["cnNo"])
            if i["status"] == "confirmed" and i["result"] == "PASS"
        }
        if inspection_id not in passed:
            raise _field(
                "firstArticleInspectionId",
                "이 신고를 원천으로 확정·합격한 초품 검사만 고를 수 있습니다.",
            )
        connection.execute(
            text(
                "UPDATE qms.change_notice SET status='VERIFIED', "
                f"first_article_inspection_id=:f WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "f": inspection_id, "id": cn_id},
        )
        return _change(connection, scoped, cn_id), "change_notice", cn_id

    return _action(
        context, "qms.change_notice.verify", key, {"id": cn_id, **values}, fn
    )


# ---------- 부적합 보고 (Q-07, DSN-14 F31) ----------

NCR_SQL = """
SELECT n.id, n.ncr_no, n.origin, n.item_code, n.lot_no, n.qty, n.defect_type_id,
       d.code defect_code, d.name defect_name, n.description, n.immediate_action,
       n.inspection_id, i.inspection_no, n.claim_id, n.source_ref, n.reported_on,
       n.status, n.closed_at, n.created_at,
       (SELECT count(*) FROM qms.capa c WHERE c.workspace_id=n.workspace_id
         AND c.generation_id=n.generation_id AND c.ncr_id=n.id) capa_count,
       (SELECT count(*) FROM qms.capa c WHERE c.workspace_id=n.workspace_id
         AND c.generation_id=n.generation_id AND c.ncr_id=n.id AND c.status='VERIFIED') verified_count
FROM qms.ncr n
LEFT JOIN qms.defect_type d ON d.workspace_id=n.workspace_id
 AND d.generation_id=n.generation_id AND d.id=n.defect_type_id
LEFT JOIN qms.inspection i ON i.workspace_id=n.workspace_id
 AND i.generation_id=n.generation_id AND i.id=n.inspection_id
WHERE n.workspace_id=:w AND n.generation_id=:g
"""

# 발생처별 근거 규칙은 DB CHECK와 같다 — 서비스는 같은 말을 사람 말로 돌려줄 뿐이다.
_NEEDS_INSPECTION = ("INCOMING", "OUTGOING")


def _ncr(
    connection: Connection, scoped: AuthContext, ncr_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.ncr WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": ncr_id},
        )
    row = (
        connection.execute(
            text(NCR_SQL + " AND n.id=:id"), {**_s(scoped), "id": ncr_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def list_ncrs(
    context: AuthContext, status: str | None, origin: str | None
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(
                    NCR_SQL + " AND (CAST(:status AS text) IS NULL OR n.status=:status)"
                    " AND (CAST(:origin AS text) IS NULL OR n.origin=:origin)"
                    " ORDER BY n.reported_on DESC, n.id DESC"
                ),
                {**_s(scoped), "status": status, "origin": origin},
            ).mappings()
        ]


def get_ncr(context: AuthContext, ncr_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _ncr(connection, scoped, ncr_id)
        if found is None:
            raise _not_found("부적합 보고")
        return {**found, "capas": _capas(connection, scoped, ncr_id)}


def ncr_sources(context: AuthContext, origin: str, month: str | None) -> dict[str, Any]:
    """발생처별 근거 후보. 검사는 QMS가, 공정 불량은 MES가 준다(1b `defects`의 첫 소비자).

    이미 부적합 보고를 만든 원천은 빼 준다 — 원천당 1건이 설계다(UK_PARTIAL).
    """
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        used = set(
            connection.execute(
                text(f"SELECT source_ref FROM qms.ncr WHERE {_S} AND origin=:o"),
                {**_s(scoped), "o": origin},
            ).scalars()
        )
        if origin == "PROCESS":
            rows = mes.defects(connection, scoped, month or f"{business_today():%Y-%m}")
            if rows is None:
                return {"mesEnabled": False, "rows": []}
            return {
                "mesEnabled": True,
                "rows": [
                    {**r, "sourceRef": ref}
                    for r in rows
                    if (ref := f"{r['lotNo']}:{r['processCode']}") not in used
                ],
            }
        kind = "INCOMING" if origin == "INCOMING" else "OUTGOING"
        taken = set(
            connection.execute(
                text(
                    f"SELECT inspection_id FROM qms.ncr WHERE {_S} AND inspection_id IS NOT NULL"
                ),
                _s(scoped),
            ).scalars()
        )
        rows = [
            _row(r)
            for r in connection.execute(
                text(
                    INSPECTION_SQL + " AND i.status='confirmed' AND i.result='FAIL'"
                    " AND i.inspection_kind=:kind ORDER BY i.confirmed_at DESC"
                ),
                {**_s(scoped), "kind": kind},
            ).mappings()
        ]
        return {
            "mesEnabled": True,
            "rows": [r for r in rows if r["id"] not in taken],
        }


def _check_origin(
    connection: Connection, scoped: AuthContext, values: dict[str, Any]
) -> None:
    origin = values["origin"]
    if origin == "CUSTOMER":
        raise _conflict(
            "고객 발생 부적합은 클레임에서 만듭니다.", "CLAIM_REQUIRED", origin=origin
        )
    if origin in _NEEDS_INSPECTION and not values.get("inspection_id"):
        raise _field("inspectionId", "근거가 되는 불합격 검사를 고르세요.")
    if origin not in _NEEDS_INSPECTION and values.get("inspection_id"):
        raise _field("inspectionId", "이 발생처에는 근거 검사를 달 수 없습니다.")
    if values.get("inspection_id"):
        found = _inspection(connection, scoped, values["inspection_id"])
        if found is None:
            raise _field("inspectionId", "검사를 찾을 수 없습니다.")
        if found["status"] != "confirmed" or found["result"] != "FAIL":
            raise _field("inspectionId", "확정·불합격한 검사만 근거가 됩니다.")


def _insert_ncr(
    connection: Connection, scoped: AuthContext, values: dict[str, Any]
) -> int:
    """부적합 보고 1행. 클레임 조사도 이 길로 들어온다(발생처 CUSTOMER·근거 클레임)."""
    return connection.execute(
        text(
            "INSERT INTO qms.ncr(workspace_id,generation_id,ncr_no,origin,item_code,lot_no,"
            "qty,defect_type_id,description,immediate_action,inspection_id,claim_id,source_ref,"
            "reported_on) "
            "VALUES (:w,:g,:no,:origin,:item,:lot,:qty,:defect,:desc,:act,:inspection,:claim,:ref,:on) "
            "RETURNING id"
        ),
        {
            **_s(scoped),
            "no": _next_no(connection, scoped, "qms.ncr", "ncr_no", "NCR"),
            "origin": values["origin"],
            "item": values["item_code"],
            "lot": values.get("lot_no"),
            "qty": values["qty"],
            "defect": values.get("defect_type_id"),
            "desc": values["description"],
            "act": values.get("immediate_action"),
            "inspection": values.get("inspection_id"),
            "claim": values.get("claim_id"),
            "ref": values.get("source_ref"),
            "on": values.get("reported_on") or business_today(),
        },
    ).scalar_one()


def create_ncr(context: AuthContext, values: dict[str, Any], key: str):
    def fn(connection: Connection, scoped: AuthContext):
        _check_origin(connection, scoped, values)
        if (
            values.get("source_ref")
            and connection.execute(
                text(
                    f"SELECT 1 FROM qms.ncr WHERE {_S} AND origin=:o AND source_ref=:ref"
                ),
                {**_s(scoped), "o": values["origin"], "ref": values["source_ref"]},
            ).first()
        ):
            raise _field("sourceRef", "이 원천으로 만든 부적합 보고가 이미 있습니다.")
        ncr_id = _insert_ncr(connection, scoped, values)
        return _ncr(connection, scoped, ncr_id), "ncr", ncr_id

    return _action(context, "qms.ncr.create", key, values, fn, 201)


_NCR_EDITABLE = ("description", "immediate_action", "qty", "defect_type_id", "lot_no")


def update_ncr(context: AuthContext, ncr_id: int, values: dict, key: str):
    """종결 전에만 고친다. 발생처·근거는 바꾸지 않는다 — 바꿀 일이면 새 보고다."""
    if not values:
        raise _fields({"description": "변경할 항목이 없습니다."})

    def fn(connection: Connection, scoped: AuthContext):
        found = _ncr(connection, scoped, ncr_id, lock=True)
        if found is None:
            raise _not_found("부적합 보고")
        if found["status"] != "OPEN":
            raise _conflict("종결한 보고는 고칠 수 없습니다.", "NCR_CLOSED")
        assignments = ",".join(f"{name}=:{name}" for name in values)
        connection.execute(
            text(f"UPDATE qms.ncr SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": ncr_id},
        )
        return _ncr(connection, scoped, ncr_id), "ncr", ncr_id

    return _action(context, "qms.ncr.update", key, {"id": ncr_id, **values}, fn)


def close_ncr(context: AuthContext, ncr_id: int, key: str):
    """연결 CAPA가 **하나 이상 있고 모두 유효성 확인**되어야 종결한다(DB_POLICY Q3)."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _ncr(connection, scoped, ncr_id, lock=True)
        if found is None:
            raise _not_found("부적합 보고")
        if found["status"] != "OPEN":
            raise _conflict("이미 종결한 보고입니다.", "NCR_CLOSED")
        total, verified = found["capaCount"], found["verifiedCount"]
        if total == 0:
            raise _conflict(
                "시정·예방 조치가 없습니다. 조치를 만들고 유효성을 확인한 뒤 종결하세요.",
                "NO_CAPA",
            )
        if verified < total:
            raise _conflict(
                "유효성을 확인하지 않은 조치가 남았습니다.",
                "CAPA_NOT_VERIFIED",
                open=total - verified,
            )
        connection.execute(
            text(
                "UPDATE qms.ncr SET status='CLOSED', closed_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": ncr_id},
        )
        return _ncr(connection, scoped, ncr_id), "ncr", ncr_id

    return _action(context, "qms.ncr.close", key, {"id": ncr_id}, fn)


# ---------- 시정·예방 조치 (Q-08, DSN-14 F32) ----------

CAPA_SQL = """
SELECT c.id, c.capa_no, c.ncr_id, n.ncr_no, n.item_code, c.kind, c.root_cause, c.action,
       c.owner_name, c.due_on, c.status, c.done_at, c.verified_at, c.verification_note,
       c.owner_hr_code, c.created_at
FROM qms.capa c
JOIN qms.ncr n ON n.workspace_id=c.workspace_id AND n.generation_id=c.generation_id
 AND n.id=c.ncr_id
WHERE c.workspace_id=:w AND c.generation_id=:g
"""


def _capas(
    connection: Connection, scoped: AuthContext, ncr_id: int
) -> list[dict[str, Any]]:
    return [
        _row(r)
        for r in connection.execute(
            text(CAPA_SQL + " AND c.ncr_id=:id ORDER BY c.id"),
            {**_s(scoped), "id": ncr_id},
        ).mappings()
    ]


def _capa(
    connection: Connection, scoped: AuthContext, capa_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.capa WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": capa_id},
        )
    row = (
        connection.execute(
            text(CAPA_SQL + " AND c.id=:id"), {**_s(scoped), "id": capa_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def list_capas(
    context: AuthContext, status: str | None, ncr_id: int | None
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(
                    CAPA_SQL
                    + " AND (CAST(:status AS text) IS NULL OR c.status=:status)"
                    " AND (CAST(:ncr AS bigint) IS NULL OR c.ncr_id=:ncr)"
                    " ORDER BY c.due_on, c.id"
                ),
                {**_s(scoped), "status": status, "ncr": ncr_id},
            ).mappings()
        ]


def get_capa(context: AuthContext, capa_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _capa(connection, scoped, capa_id)
        if found is None:
            raise _not_found("시정·예방 조치")
        return found


def create_capa(context: AuthContext, values: dict[str, Any], key: str):
    """조치는 부적합 보고에 속한다. 종결한 보고에는 더 달지 않는다."""

    def fn(connection: Connection, scoped: AuthContext):
        parent = _ncr(connection, scoped, values["ncr_id"], lock=True)
        if parent is None:
            raise _field("ncrId", "부적합 보고를 찾을 수 없습니다.")
        if parent["status"] != "OPEN":
            raise _conflict("종결한 보고에는 조치를 더할 수 없습니다.", "NCR_CLOSED")
        capa_id = connection.execute(
            text(
                "INSERT INTO qms.capa(workspace_id,generation_id,capa_no,ncr_id,kind,root_cause,"
                "action,owner_name,due_on) VALUES (:w,:g,:no,:ncr,:kind,:cause,:act,:owner,:due) "
                "RETURNING id"
            ),
            {
                **_s(scoped),
                "no": _next_no(connection, scoped, "qms.capa", "capa_no", "CA"),
                "ncr": values["ncr_id"],
                "kind": values["kind"],
                "cause": values["root_cause"],
                "act": values["action"],
                "owner": values["owner_name"],
                "due": values["due_on"],
            },
        ).scalar_one()
        return _capa(connection, scoped, capa_id), "capa", capa_id

    return _action(context, "qms.capa.create", key, values, fn, 201)


def update_capa(context: AuthContext, capa_id: int, values: dict, key: str):
    """완료 전에만 고친다. 완료·확인 뒤의 기록은 그대로 둔다."""
    if not values:
        raise _fields({"action": "변경할 항목이 없습니다."})

    def fn(connection: Connection, scoped: AuthContext):
        found = _capa(connection, scoped, capa_id, lock=True)
        if found is None:
            raise _not_found("시정·예방 조치")
        if found["status"] != "OPEN":
            raise _conflict(
                "완료한 조치는 고칠 수 없습니다.",
                "CAPA_NOT_OPEN",
                status=found["status"],
            )
        assignments = ",".join(f"{name}=:{name}" for name in values)
        connection.execute(
            text(f"UPDATE qms.capa SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": capa_id},
        )
        return _capa(connection, scoped, capa_id), "capa", capa_id

    return _action(context, "qms.capa.update", key, {"id": capa_id, **values}, fn)


def complete_capa(context: AuthContext, capa_id: int, key: str):
    def fn(connection: Connection, scoped: AuthContext):
        found = _capa(connection, scoped, capa_id, lock=True)
        if found is None:
            raise _not_found("시정·예방 조치")
        if found["status"] != "OPEN":
            raise _conflict(
                "이미 완료한 조치입니다.", "CAPA_NOT_OPEN", status=found["status"]
            )
        connection.execute(
            text(
                "UPDATE qms.capa SET status='DONE', done_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": capa_id},
        )
        return _capa(connection, scoped, capa_id), "capa", capa_id

    return _action(context, "qms.capa.complete", key, {"id": capa_id}, fn)


def verify_capa(context: AuthContext, capa_id: int, values: dict, key: str):
    """완료한 조치의 유효성을 확인한다. **무효면 새 조치를 만든다** — 되돌리지 않는다."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _capa(connection, scoped, capa_id, lock=True)
        if found is None:
            raise _not_found("시정·예방 조치")
        if found["status"] != "DONE":
            raise _conflict(
                "완료한 조치만 확인할 수 있습니다.",
                "CAPA_NOT_DONE",
                status=found["status"],
            )
        note = (values.get("note") or "").strip()
        if len(note) < 2:
            raise _field("note", "확인 내용을 두 글자 이상 적어 주세요.")
        connection.execute(
            text(
                "UPDATE qms.capa SET status=:s, verified_at=clock_timestamp(), "
                f"verification_note=:note WHERE {_S} AND id=:id"
            ),
            {
                **_s(scoped),
                "s": "VERIFIED" if values["effective"] else "INEFFECTIVE",
                "note": note,
                "id": capa_id,
            },
        )
        return _capa(connection, scoped, capa_id), "capa", capa_id

    return _action(context, "qms.capa.verify", key, {"id": capa_id, **values}, fn)


# ---------- 고객 클레임 (Q-09, DSN-14 F41~F43) ----------

CLAIM_SQL = """
SELECT c.id, c.claim_no, c.customer_code, c.received_on, c.item_code, c.lot_no, c.qty,
       c.severity, c.description, c.return_ref, c.status, c.response, c.responded_on,
       c.closed_at, c.crm_inquiry_no, c.created_at,
       (SELECT count(*) FROM qms.ncr n WHERE n.workspace_id=c.workspace_id
         AND n.generation_id=c.generation_id AND n.claim_id=c.id) ncr_count
FROM qms.claim c WHERE c.workspace_id=:w AND c.generation_id=:g
"""


def _claim(
    connection: Connection, scoped: AuthContext, claim_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.claim WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": claim_id},
        )
    row = (
        connection.execute(
            text(CLAIM_SQL + " AND c.id=:id"), {**_s(scoped), "id": claim_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def list_claims(
    context: AuthContext, status: str | None, customer_code: str | None
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(
                    CLAIM_SQL
                    + " AND (CAST(:status AS text) IS NULL OR c.status=:status)"
                    " AND (CAST(:customer AS text) IS NULL OR c.customer_code=:customer)"
                    " ORDER BY c.received_on DESC, c.id DESC"
                ),
                {**_s(scoped), "status": status, "customer": customer_code},
            ).mappings()
        ]


def get_claim(context: AuthContext, claim_id: int) -> dict[str, Any]:
    """클레임 1건 + 연결 부적합 + **LOT 역추적**(F43). MES가 꺼졌거나 LOT이 없으면 trace는 None."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _claim(connection, scoped, claim_id)
        if found is None:
            raise _not_found("클레임")
        ncrs = [
            _row(r)
            for r in connection.execute(
                text(NCR_SQL + " AND n.claim_id=:id ORDER BY n.id"),
                {**_s(scoped), "id": claim_id},
            ).mappings()
        ]
        trace = (
            mes.lot_trace(connection, scoped, found["lotNo"])
            if found["lotNo"]
            else None
        )
        return {
            **found,
            "ncrs": ncrs,
            "trace": trace,
            "mesEnabled": mes.enabled(connection, scoped),
        }


def customers(context: AuthContext) -> list[dict[str, Any]]:
    """클레임을 걸 고객 목록. ERP가 꺼져 있으면 빈 목록이고 코드를 직접 적는다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return erp.partners(connection, scoped, "CUSTOMER") or []


def create_claim(context: AuthContext, values: dict[str, Any], key: str):
    def fn(connection: Connection, scoped: AuthContext):
        claim_id = connection.execute(
            text(
                "INSERT INTO qms.claim(workspace_id,generation_id,claim_no,customer_code,"
                "received_on,item_code,lot_no,qty,severity,description,return_ref) "
                "VALUES (:w,:g,:no,:customer,:on,:item,:lot,:qty,:severity,:desc,:ret) RETURNING id"
            ),
            {
                **_s(scoped),
                "no": _next_no(connection, scoped, "qms.claim", "claim_no", "CL"),
                "customer": values["customer_code"],
                "on": values.get("received_on") or business_today(),
                "item": values["item_code"],
                "lot": values.get("lot_no"),
                "qty": values["qty"],
                "severity": values["severity"],
                "desc": values["description"],
                "ret": values.get("return_ref"),
            },
        ).scalar_one()
        return _claim(connection, scoped, claim_id), "claim", claim_id

    return _action(context, "qms.claim.create", key, values, fn, 201)


def update_claim(context: AuthContext, claim_id: int, values: dict, key: str):
    """회신 전에만 고친다. 회신·종결한 클레임은 고객에게 나간 기록이라 바꾸지 않는다."""
    if not values:
        raise _fields({"description": "변경할 항목이 없습니다."})

    def fn(connection: Connection, scoped: AuthContext):
        found = _claim(connection, scoped, claim_id, lock=True)
        if found is None:
            raise _not_found("클레임")
        if found["status"] not in ("RECEIVED", "INVESTIGATING"):
            raise _conflict(
                "회신한 클레임은 고칠 수 없습니다.",
                "CLAIM_RESPONDED",
                status=found["status"],
            )
        assignments = ",".join(f"{name}=:{name}" for name in values)
        connection.execute(
            text(f"UPDATE qms.claim SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": claim_id},
        )
        return _claim(connection, scoped, claim_id), "claim", claim_id

    return _action(context, "qms.claim.update", key, {"id": claim_id, **values}, fn)


def start_investigation(
    context: AuthContext, claim_id: int, values: dict[str, Any], key: str
):
    """조사 시작 — **고객 발생 부적합 보고를 같은 트랜잭션에서 만든다**(DB_POLICY Q4).

    클레임은 고객이 말한 것이고, 부적합 보고는 우리가 확인한 것이다. 둘을 갈라 두면
    조사 없이 회신하는 길이 열린다. 그래서 조사 시작 = 부적합 보고 생성이다.
    """

    def fn(connection: Connection, scoped: AuthContext):
        found = _claim(connection, scoped, claim_id, lock=True)
        if found is None:
            raise _not_found("클레임")
        if found["status"] != "RECEIVED":
            raise _conflict(
                "접수 상태의 클레임만 조사를 시작합니다.",
                "NOT_RECEIVED",
                status=found["status"],
            )
        ncr_id = _insert_ncr(
            connection,
            scoped,
            {
                "origin": "CUSTOMER",
                "item_code": found["itemCode"],
                "lot_no": found["lotNo"],
                "qty": values.get("qty") or found["qty"],
                "defect_type_id": values.get("defect_type_id"),
                "description": values["description"],
                "immediate_action": values.get("immediate_action"),
                "claim_id": claim_id,
            },
        )
        connection.execute(
            text(f"UPDATE qms.claim SET status='INVESTIGATING' WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": claim_id},
        )
        return (
            {**_claim(connection, scoped, claim_id), "ncrId": ncr_id},
            "claim",
            claim_id,
        )

    return _action(
        context, "qms.claim.investigate", key, {"id": claim_id, **values}, fn
    )


def respond_claim(context: AuthContext, claim_id: int, values: dict, key: str):
    """고객 회신. **조사(부적합 보고)를 거친 뒤에만** 회신한다 — 확인 없이 답하지 않는다."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _claim(connection, scoped, claim_id, lock=True)
        if found is None:
            raise _not_found("클레임")
        if found["status"] != "INVESTIGATING":
            raise _conflict(
                "조사 중인 클레임만 회신합니다.",
                "NOT_INVESTIGATING",
                status=found["status"],
            )
        connection.execute(
            text(
                "UPDATE qms.claim SET status='RESPONDED', response=:res, responded_on=:on "
                f"WHERE {_S} AND id=:id"
            ),
            {
                **_s(scoped),
                "res": values["response"],
                "on": values.get("responded_on") or business_today(),
                "id": claim_id,
            },
        )
        return _claim(connection, scoped, claim_id), "claim", claim_id

    return _action(context, "qms.claim.respond", key, {"id": claim_id, **values}, fn)


def close_claim(context: AuthContext, claim_id: int, key: str):
    """연결 부적합이 모두 종결되어야 클레임을 닫는다 — 조치가 남은 채로 닫지 않는다."""

    def fn(connection: Connection, scoped: AuthContext):
        found = _claim(connection, scoped, claim_id, lock=True)
        if found is None:
            raise _not_found("클레임")
        if found["status"] != "RESPONDED":
            raise _conflict(
                "회신한 클레임만 종결합니다.", "NOT_RESPONDED", status=found["status"]
            )
        open_ncrs = connection.execute(
            text(
                f"SELECT count(*) FROM qms.ncr WHERE {_S} AND claim_id=:id AND status='OPEN'"
            ),
            {**_s(scoped), "id": claim_id},
        ).scalar_one()
        if open_ncrs:
            raise _conflict(
                "종결하지 않은 부적합 보고가 남았습니다.",
                "NCR_OPEN",
                open=open_ncrs,
            )
        connection.execute(
            text(
                "UPDATE qms.claim SET status='CLOSED', closed_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": claim_id},
        )
        return _claim(connection, scoped, claim_id), "claim", claim_id

    return _action(context, "qms.claim.close", key, {"id": claim_id}, fn)


# ---------- 공급처 품질 (Q-10, DSN-14 F05·F14·F51) ----------

LEVEL_SQL = """
SELECT l.id, l.partner_code, l.item_code, l.level, l.valid_from, l.reason, l.rating_id,
       r.rating_month, r.grade, l.created_at
FROM qms.supplier_level l
LEFT JOIN qms.supplier_rating r ON r.workspace_id=l.workspace_id
 AND r.generation_id=l.generation_id AND r.id=l.rating_id
WHERE l.workspace_id=:w AND l.generation_id=:g
"""
SCAR_SQL = """
SELECT s.id, s.scar_no, s.partner_code, s.inspection_id, i.inspection_no, s.ncr_id,
       n.ncr_no, s.issued_on, s.due_on, s.response, s.responded_on, s.status,
       s.closed_at, s.created_at
FROM qms.scar s
LEFT JOIN qms.inspection i ON i.workspace_id=s.workspace_id
 AND i.generation_id=s.generation_id AND i.id=s.inspection_id
LEFT JOIN qms.ncr n ON n.workspace_id=s.workspace_id
 AND n.generation_id=s.generation_id AND n.id=s.ncr_id
WHERE s.workspace_id=:w AND s.generation_id=:g
"""

# 등급 기준은 설계에 수치가 없다. **불합격 LOT 비율**로 가르고, 시정 요구가 있으면 한 단계 내린다.
_GRADE_BANDS = ((Decimal(0), "A"), (Decimal("0.05"), "B"), (Decimal("0.10"), "C"))
# 연속 합격 10 LOT이면 면제, 연속 불합격 2 LOT이면 강화를 제안한다(DSN-14 Q5).
_EXEMPT_RUN, _TIGHTEN_RUN = 10, 2


def _grade(lot_count: int, failed: int, scar_count: int) -> str:
    if lot_count == 0:
        return "A"
    rate = Decimal(failed) / Decimal(lot_count)
    grade = next((g for limit, g in _GRADE_BANDS if rate <= limit), "D")
    if scar_count:  # 시정 요구가 있었으면 한 단계 내린다. D는 더 내려갈 곳이 없다.
        grade = {"A": "B", "B": "C", "C": "D", "D": "D"}[grade]
    return grade


def _suggested_level(results: list[str]) -> str | None:
    """최신순 판정 목록에서 앞쪽 연속만 본다. 섞여 있으면 제안하지 않는다."""
    if len(results) >= _EXEMPT_RUN and all(r == "PASS" for r in results[:_EXEMPT_RUN]):
        return "EXEMPT"
    if len(results) >= _TIGHTEN_RUN and all(
        r == "FAIL" for r in results[:_TIGHTEN_RUN]
    ):
        return "TIGHTENED"
    return None


def suppliers(context: AuthContext) -> list[dict[str, Any]]:
    """공급처 목록. ERP가 꺼져 있으면 빈 목록이고 코드를 직접 적는다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return erp.partners(connection, scoped, "SUPPLIER") or []


def supplier_levels(
    context: AuthContext, partner_code: str | None
) -> list[dict[str, Any]]:
    """검사 수준 이력. **현재 수준은 저장하지 않는다** — 적용일이 오늘 이하인 최신 행이다."""
    today = business_today()
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = [
            _row(r)
            for r in connection.execute(
                text(
                    LEVEL_SQL
                    + " AND (CAST(:code AS text) IS NULL OR l.partner_code=:code)"
                    " ORDER BY l.partner_code, l.item_code NULLS FIRST,"
                    " l.valid_from DESC, l.id DESC"
                ),
                {**_s(scoped), "code": partner_code},
            ).mappings()
        ]
    current: set[tuple[str, str | None]] = set()
    for row in rows:
        scope_key = (row["partnerCode"], row["itemCode"])
        applied = date.fromisoformat(row["validFrom"]) <= today
        row["isCurrent"] = applied and scope_key not in current
        if row["isCurrent"]:
            current.add(scope_key)
    return rows


def create_supplier_level(context: AuthContext, values: dict[str, Any], key: str):
    def fn(connection: Connection, scoped: AuthContext):
        if connection.execute(
            text(
                f"SELECT 1 FROM qms.supplier_level WHERE {_S} AND partner_code=:code "
                "AND item_code IS NOT DISTINCT FROM :item AND valid_from=:on"
            ),
            {
                **_s(scoped),
                "code": values["partner_code"],
                "item": values.get("item_code"),
                "on": values["valid_from"],
            },
        ).first():
            raise _field("validFrom", "같은 공급처·품목·적용일의 수준이 이미 있습니다.")
        row_id = connection.execute(
            text(
                "INSERT INTO qms.supplier_level(workspace_id,generation_id,partner_code,"
                "item_code,level,valid_from,reason,rating_id) "
                "VALUES (:w,:g,:code,:item,:level,:on,:reason,:rating) RETURNING id"
            ),
            {
                **_s(scoped),
                "code": values["partner_code"],
                "item": values.get("item_code"),
                "level": values["level"],
                "on": values["valid_from"],
                "reason": values["reason"],
                "rating": values.get("rating_id"),
            },
        ).scalar_one()
        row = (
            connection.execute(
                text(LEVEL_SQL + " AND l.id=:id"), {**_s(scoped), "id": row_id}
            )
            .mappings()
            .one()
        )
        return _row(row), "supplier_level", row_id

    return _action(context, "qms.supplier_level.create", key, values, fn, 201)


def supplier_ratings(context: AuthContext, month: str | None) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(
                    f"SELECT * FROM qms.supplier_rating WHERE {_S} "
                    "AND (CAST(:month AS text) IS NULL OR rating_month=:month) "
                    "ORDER BY rating_month DESC, partner_code"
                ),
                {**_s(scoped), "month": month},
            ).mappings()
        ]


def calculate_ratings(context: AuthContext, month: str, key: str):
    """그 달 **수입 검사**로 공급처를 평가한다(F51). 다시 계산하면 그 달 행을 덮어쓴다.

    수입 검사가 아직 없는 공간에서는 평가할 공급처가 없어 빈 목록이 나온다 — 0점이 아니라
    '아직 아님'이다. 등급을 확정하는 것은 사람이고, 이 함수는 제안까지만 한다.
    """

    def fn(connection: Connection, scoped: AuthContext):
        rows = connection.execute(
            text(
                "SELECT partner_code, count(*) lot_count, "
                " count(*) FILTER (WHERE result='FAIL') failed, "
                " COALESCE(sum(defect_count), 0) defects, COALESCE(sum(sample_qty), 0) sampled "
                f"FROM qms.inspection WHERE {_S} AND inspection_kind='INCOMING' "
                "  AND status='confirmed' AND partner_code IS NOT NULL "
                "  AND inspection_month=:month GROUP BY partner_code ORDER BY partner_code"
            ),
            {**_s(scoped), "month": month},
        ).mappings()
        saved = []
        for row in rows:
            partner = row["partner_code"]
            scar_count = connection.execute(
                text(
                    f"SELECT count(*) FROM qms.scar WHERE {_S} AND partner_code=:code "
                    "AND to_char(issued_on, 'YYYY-MM')=:month"
                ),
                {**_s(scoped), "code": partner, "month": month},
            ).scalar_one()
            sampled = Decimal(str(row["sampled"]))
            ppm = (
                Decimal(0)
                if sampled == 0
                else (Decimal(str(row["defects"])) * 1000000 / sampled)
            )
            recent = list(
                connection.execute(
                    text(
                        f"SELECT result FROM qms.inspection WHERE {_S} "
                        "AND inspection_kind='INCOMING' AND status='confirmed' "
                        "AND partner_code=:code ORDER BY confirmed_at DESC, id DESC LIMIT :n"
                    ),
                    {**_s(scoped), "code": partner, "n": _EXEMPT_RUN},
                ).scalars()
            )
            grade = _grade(row["lot_count"], row["failed"], scar_count)
            connection.execute(
                text(
                    "INSERT INTO qms.supplier_rating(workspace_id,generation_id,rating_month,"
                    "partner_code,lot_count,failed_lot_count,defect_ppm,scar_count,grade,"
                    "suggested_level) VALUES (:w,:g,:month,:code,:lots,:failed,:ppm,:scars,"
                    ":grade,:suggest) "
                    "ON CONFLICT (workspace_id,generation_id,rating_month,partner_code) "
                    "DO UPDATE SET lot_count=EXCLUDED.lot_count, "
                    " failed_lot_count=EXCLUDED.failed_lot_count, defect_ppm=EXCLUDED.defect_ppm, "
                    " scar_count=EXCLUDED.scar_count, grade=EXCLUDED.grade, "
                    " suggested_level=EXCLUDED.suggested_level"
                ),
                {
                    **_s(scoped),
                    "month": month,
                    "code": partner,
                    "lots": row["lot_count"],
                    "failed": row["failed"],
                    "ppm": ppm.quantize(Decimal("0.1")),
                    "scars": scar_count,
                    "grade": grade,
                    "suggest": _suggested_level(recent),
                },
            )
            saved.append(partner)
        return {"month": month, "partners": saved}, "supplier_rating", len(saved)

    return _action(context, "qms.supplier_rating.calculate", key, {"month": month}, fn)


def list_scars(context: AuthContext, status: str | None) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(
                    SCAR_SQL
                    + " AND (CAST(:status AS text) IS NULL OR s.status=:status)"
                    " ORDER BY s.issued_on DESC, s.id DESC"
                ),
                {**_s(scoped), "status": status},
            ).mappings()
        ]


def _scar(
    connection: Connection, scoped: AuthContext, scar_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM qms.scar WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": scar_id},
        )
    row = (
        connection.execute(
            text(SCAR_SQL + " AND s.id=:id"), {**_s(scoped), "id": scar_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def create_scar(context: AuthContext, values: dict[str, Any], key: str):
    """공급처 시정 요구. **통보는 기록만 한다 — 메일이나 팩스를 보내지 않는다**(설계 F14)."""

    def fn(connection: Connection, scoped: AuthContext):
        if values.get("ncr_id"):
            parent = _ncr(connection, scoped, values["ncr_id"])
            if parent is None:
                raise _field("ncrId", "부적합 보고를 찾을 수 없습니다.")
        issued_on = values.get("issued_on") or business_today()
        if values["due_on"] < issued_on:
            raise _field("dueOn", "회신 기한은 발행일 이후여야 합니다.")
        scar_id = connection.execute(
            text(
                "INSERT INTO qms.scar(workspace_id,generation_id,scar_no,partner_code,"
                "inspection_id,ncr_id,issued_on,due_on) "
                "VALUES (:w,:g,:no,:code,:inspection,:ncr,:on,:due) RETURNING id"
            ),
            {
                **_s(scoped),
                "no": _next_no(connection, scoped, "qms.scar", "scar_no", "SC"),
                "code": values["partner_code"],
                "inspection": values.get("inspection_id"),
                "ncr": values.get("ncr_id"),
                "on": issued_on,
                "due": values["due_on"],
            },
        ).scalar_one()
        return _scar(connection, scoped, scar_id), "scar", scar_id

    return _action(context, "qms.scar.create", key, values, fn, 201)


def respond_scar(context: AuthContext, scar_id: int, values: dict, key: str):
    def fn(connection: Connection, scoped: AuthContext):
        found = _scar(connection, scoped, scar_id, lock=True)
        if found is None:
            raise _not_found("시정 요구")
        if found["status"] != "OPEN":
            raise _conflict(
                "회신을 받은 요구입니다.", "SCAR_RESPONDED", status=found["status"]
            )
        connection.execute(
            text(
                "UPDATE qms.scar SET status='RESPONDED', response=:res, responded_on=:on "
                f"WHERE {_S} AND id=:id"
            ),
            {
                **_s(scoped),
                "res": values["response"],
                "on": values.get("responded_on") or business_today(),
                "id": scar_id,
            },
        )
        return _scar(connection, scoped, scar_id), "scar", scar_id

    return _action(context, "qms.scar.respond", key, {"id": scar_id, **values}, fn)


def close_scar(context: AuthContext, scar_id: int, key: str):
    def fn(connection: Connection, scoped: AuthContext):
        found = _scar(connection, scoped, scar_id, lock=True)
        if found is None:
            raise _not_found("시정 요구")
        if found["status"] != "RESPONDED":
            raise _conflict(
                "회신을 받은 요구만 종결합니다.",
                "SCAR_NOT_RESPONDED",
                status=found["status"],
            )
        connection.execute(
            text(
                "UPDATE qms.scar SET status='CLOSED', closed_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": scar_id},
        )
        return _scar(connection, scoped, scar_id), "scar", scar_id

    return _action(context, "qms.scar.close", key, {"id": scar_id}, fn)
