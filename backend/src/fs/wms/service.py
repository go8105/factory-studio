"""WMS 업무 규칙 (FS-024 모듈 설계 3·5·6장).

- 원장: 현재고 = 확정(posted) 전표 이동 합. 잔량을 저장하지 않고, 확정 전표·이동은 바꾸지 않는다.
- 원천 반영(TX-W1): MES·ERP의 확정 기록을 fs.mes/fs.erp interface로만 읽어(D9) 원천 1건 = 전표 1건으로
  만들면서 확정한다. source_key가 같으면 기존 전표를 돌려준다(D14 멱등). MES·ERP 데이터는 바꾸지 않는다.
- 음수 허용(D15): 잔량을 확인하지 않는다. 그래서 잔량 행 잠금이 없고 원장 INSERT만 한다.
- 수동 전표(TX-W2): 기초·조정·이동 초안 → 확정. 이동은 품목·LOT별 합 0(보낼 −, 받을 + 한 쌍).
- 매입 취소 반영(TX-W3): 확정 후 취소된 ERP 매입의 반영 전표를 되돌림 전표로 상쇄한다.

쓰기는 write_scope의 공간 잠금 뒤에 실행되므로 발번·같은 원천 반영이 공간 안에서 직렬화된다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.erp import interface as erp
from fs.mes import interface as mes

MODULE = "wms"
SEOUL = ZoneInfo("Asia/Seoul")
_S = "workspace_id=:w AND generation_id=:g"
Q3 = Decimal("0.001")
SOURCE_KINDS = ("MES_RECEIPT", "MES_ISSUE", "ERP_SHIPMENT", "ERP_PURCHASE")
SOURCE_MODULE = {
    "MES_RECEIPT": "mes",
    "MES_ISSUE": "mes",
    "ERP_SHIPMENT": "erp",
    "ERP_PURCHASE": "erp",
}


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


def _fields(fields: dict[str, str]) -> ApiError:
    return ApiError(
        400, "VALIDATION_FAILED", "입력값을 확인해 주세요.", {"fields": fields}
    )


def _conflict(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


def _not_found(label: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{label}을(를) 찾을 수 없습니다.")


def _referenced(message: str, label: str, count: int) -> ApiError:
    return ApiError(
        409,
        "REFERENCED_BY_OTHERS",
        message,
        {"references": [{"label": label, "count": count}]},
    )


Action = Callable[[Connection, AuthContext], tuple[dict[str, Any], str, int]]


# 공통 엔진(fs.common.engine.action): 공간 잠금 → 멱등 영수증 → 처리 → 영수증 저장
_action = partial(action, MODULE)


def _next_no(
    connection: Connection, scoped: AuthContext, on: date | None = None
) -> str:
    """WD-YYYYMMDD-NNN. 공간 잠금 안에서만 부른다."""
    stem = f"WD-{on or business_today():%Y%m%d}-"
    used = connection.execute(
        text(
            f"SELECT COALESCE(max(CAST(substring(document_no FROM 13) AS bigint)),0) FROM wms.stock_document WHERE {_S} AND document_no LIKE :stem"
        ),
        {**_s(scoped), "stem": stem + "%"},
    ).scalar_one()
    return f"{stem}{used + 1:03d}"


def _qty(value: str) -> Decimal:
    return Decimal(value).quantize(Q3)


def _seoul_day(stamp: str) -> date:
    return datetime.fromisoformat(stamp).astimezone(SEOUL).date()


# ---------- 창고·위치 (W-06) ----------

WAREHOUSE_SQL = f"""
SELECT h.id, h.code, h.name, h.purpose, h.is_active, h.created_at,
       (SELECT count(*) FROM wms.storage_location l
         WHERE l.workspace_id=h.workspace_id AND l.generation_id=h.generation_id AND l.warehouse_id=h.id) location_count
FROM wms.warehouse h WHERE h.{_S.replace(" AND ", " AND h.")}
"""
LOCATION_SQL = """
SELECT l.id, l.warehouse_id, h.code warehouse_code, l.code, l.name, l.is_default, l.is_active, l.location_type,
       (SELECT count(*) FROM wms.stock_move m
         WHERE m.workspace_id=l.workspace_id AND m.generation_id=l.generation_id AND m.location_id=l.id) move_count
FROM wms.storage_location l
JOIN wms.warehouse h ON h.workspace_id=l.workspace_id AND h.generation_id=l.generation_id AND h.id=l.warehouse_id
WHERE l.workspace_id=:w AND l.generation_id=:g
"""


def _warehouse(connection, scoped, row_id: int) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(WAREHOUSE_SQL + " AND h.id=:id"), {**_s(scoped), "id": row_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def _location(connection, scoped, row_id: int) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(LOCATION_SQL + " AND l.id=:id"), {**_s(scoped), "id": row_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else _row(row)


def list_warehouses(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(WAREHOUSE_SQL + " ORDER BY h.code"), _s(scoped)
            ).mappings()
        ]


def _purpose_taken(connection, scoped, purpose: str, except_id: int = 0) -> bool:
    return bool(
        connection.execute(
            text(
                f"SELECT 1 FROM wms.warehouse WHERE {_S} AND purpose=:p AND is_active AND id<>:id"
            ),
            {**_s(scoped), "p": purpose, "id": except_id},
        ).first()
    )


def create_warehouse(context: AuthContext, values: dict, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        if connection.execute(
            text(f"SELECT 1 FROM wms.warehouse WHERE {_S} AND code=:code"),
            {**_s(scoped), "code": values["code"]},
        ).first():
            raise _fields({"code": "이미 사용 중인 코드입니다."})
        if values["is_active"] and _purpose_taken(
            connection, scoped, values["purpose"]
        ):
            raise _fields(
                {
                    "purpose": "같은 용도의 사용 중인 창고가 있습니다. 원천 반영 창고가 겹칩니다."
                }
            )
        row_id = connection.execute(
            text(
                "INSERT INTO wms.warehouse(workspace_id,generation_id,code,name,purpose,is_active) "
                "VALUES (:w,:g,:code,:name,:purpose,:is_active) RETURNING id"
            ),
            {**_s(scoped), **values},
        ).scalar_one()
        return _warehouse(connection, scoped, row_id), "warehouse", row_id

    return _action(context, "wms.warehouse.create", key, values, fn, 201)


def update_warehouse(
    context: AuthContext, row_id: int, values: dict, key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def fn(connection, scoped):
        found = _warehouse(connection, scoped, row_id)
        if found is None:
            raise _not_found("창고")
        if values.get("is_active") and _purpose_taken(
            connection, scoped, found["purpose"], row_id
        ):
            raise _fields(
                {
                    "isActive": "같은 용도의 사용 중인 창고가 있습니다. 원천 반영 창고가 겹칩니다."
                }
            )
        if values.get("is_active") is False:
            from fs.wms.receiving import guard_master

            guard_master(connection, scoped, "warehouse", row_id)
        sets = ", ".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE wms.warehouse SET {sets} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": row_id},
        )
        return _warehouse(connection, scoped, row_id), "warehouse", row_id

    return _action(context, f"wms.warehouse.update:{row_id}", key, values, fn)


def list_locations(context: AuthContext, warehouse_id: int) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if _warehouse(connection, scoped, warehouse_id) is None:
            raise _not_found("창고")
        return [
            _row(r)
            for r in connection.execute(
                text(LOCATION_SQL + " AND l.warehouse_id=:h ORDER BY l.code"),
                {**_s(scoped), "h": warehouse_id},
            ).mappings()
        ]


def _clear_default(connection, scoped, warehouse_id: int) -> None:
    connection.execute(
        text(
            f"UPDATE wms.storage_location SET is_default=false WHERE {_S} AND warehouse_id=:h AND is_default"
        ),
        {**_s(scoped), "h": warehouse_id},
    )


def create_location(
    context: AuthContext, warehouse_id: int, values: dict, key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        if _warehouse(connection, scoped, warehouse_id) is None:
            raise _not_found("창고")
        if connection.execute(
            text(
                f"SELECT 1 FROM wms.storage_location WHERE {_S} AND warehouse_id=:h AND code=:code"
            ),
            {**_s(scoped), "h": warehouse_id, "code": values["code"]},
        ).first():
            raise _fields({"code": "이 창고에 이미 있는 위치 코드입니다."})
        has_default = connection.execute(
            text(
                f"SELECT 1 FROM wms.storage_location WHERE {_S} AND warehouse_id=:h AND is_default"
            ),
            {**_s(scoped), "h": warehouse_id},
        ).first()
        location_type = values.get("location_type", "NORMAL")
        if location_type == "QUARANTINE" and values["is_default"]:
            raise _fields({"isDefault": "격리 위치는 기본 위치가 될 수 없습니다."})
        default = location_type == "NORMAL" and (
            values["is_default"] or not has_default
        )
        if default:
            _clear_default(connection, scoped, warehouse_id)
        row_id = connection.execute(
            text(
                "INSERT INTO wms.storage_location(workspace_id,generation_id,warehouse_id,code,name,is_default,location_type) "
                "VALUES (:w,:g,:h,:code,:name,:d,:lt) RETURNING id"
            ),
            {
                **_s(scoped),
                "h": warehouse_id,
                "code": values["code"],
                "name": values["name"],
                "d": default,
                "lt": location_type,
            },
        ).scalar_one()
        return _location(connection, scoped, row_id), "storage_location", row_id

    return _action(context, f"wms.location.create:{warehouse_id}", key, values, fn, 201)


def update_location(
    context: AuthContext, row_id: int, values: dict, key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def fn(connection, scoped):
        found = _location(connection, scoped, row_id)
        if found is None:
            raise _not_found("위치")
        location_type = values.get("location_type", found["locationType"])
        if location_type != found["locationType"]:
            from fs.wms.receiving import guard_master

            guard_master(connection, scoped, "location", row_id, all_history=True)
            if found["moveCount"]:
                raise _referenced(
                    "이동 이력이 있는 위치 유형은 바꿀 수 없습니다.",
                    "재고 이동",
                    found["moveCount"],
                )
        if values.get("is_active") is False:
            from fs.wms.receiving import guard_master

            guard_master(connection, scoped, "location", row_id)
        default = values.get("is_default", found["isDefault"])
        if default and location_type == "QUARANTINE":
            raise _fields({"isDefault": "격리 위치는 기본 위치가 될 수 없습니다."})
        active = values.get("is_active", found["isActive"])
        if found["isDefault"] and values.get("is_default") is False:
            raise _fields(
                {
                    "isDefault": "다른 위치를 기본으로 지정하면 이 위치의 기본 지정이 풀립니다."
                }
            )
        if default and not active:
            raise _fields({"isActive": "기본 위치는 사용 안 함으로 바꿀 수 없습니다."})
        if values.get("is_default") and not found["isDefault"]:
            _clear_default(connection, scoped, found["warehouseId"])
        sets = ", ".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE wms.storage_location SET {sets} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": row_id},
        )
        return _location(connection, scoped, row_id), "storage_location", row_id

    return _action(context, f"wms.location.update:{row_id}", key, values, fn)


def delete_location(context: AuthContext, row_id: int, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        found = _location(connection, scoped, row_id)
        if found is None:
            raise _not_found("위치")
        from fs.wms.receiving import guard_master

        guard_master(connection, scoped, "location", row_id, all_history=True)
        if found["moveCount"]:
            raise _referenced(
                "이동이 있는 위치는 지울 수 없습니다. 사용 안 함으로 바꾸세요.",
                "재고 이동",
                found["moveCount"],
            )
        if found["isDefault"]:
            raise _conflict(
                "기본 위치는 지울 수 없습니다. 다른 위치를 기본으로 지정하세요.",
                "DEFAULT_LOCATION",
            )
        connection.execute(
            text(f"DELETE FROM wms.storage_location WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": row_id},
        )
        return {"id": row_id, "deleted": True}, "storage_location", row_id

    return _action(context, f"wms.location.delete:{row_id}", key, {}, fn)


# ---------- 품목·단위 (W-07) ----------

ITEM_SQL = """
SELECT i.id, i.item_code, i.name, i.base_unit, i.item_class, i.lot_tracked,
       i.shelf_life_days, i.storage_condition, i.safety_stock, i.max_stock,
       i.abc_class, i.plm_part_no, i.plm_revision, i.is_active,
       (SELECT count(*) FROM wms.stock_move m
         WHERE m.workspace_id=i.workspace_id AND m.generation_id=i.generation_id AND m.item_id=i.id) move_count
FROM wms.item i WHERE i.workspace_id=:w AND i.generation_id=:g
"""
CONVERSION_SQL = f"""
SELECT id, item_id, from_unit, factor FROM wms.item_unit_conversion WHERE {_S}
"""


def _validate_item_rules(values: dict) -> None:
    part_no = values.get("plm_part_no")
    revision = values.get("plm_revision")
    if (part_no is None) != (revision is None):
        raise _fields(
            {"plmPartNo": "PLM 품번과 리비전은 둘 다 입력하거나 둘 다 비워야 합니다."}
        )
    safety = values.get("safety_stock")
    max_s = values.get("max_stock")
    if safety is not None and max_s is not None:
        from decimal import Decimal

        if Decimal(str(max_s)) < Decimal(str(safety)):
            raise _fields({"maxStock": "최대재고는 안전재고보다 크거나 같아야 합니다."})
    days = values.get("shelf_life_days")
    if days is not None and int(days) <= 0:
        raise _fields({"shelfLifeDays": "유효기간 일수는 1일 이상이어야 합니다."})
    abc = values.get("abc_class")
    if abc is not None and abc not in ("A", "B", "C"):
        raise _fields({"abcClass": "ABC 등급은 A, B, C 중 하나여야 합니다."})


def _item(connection, scoped, row_id: int) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(ITEM_SQL + " AND i.id=:id"), {**_s(scoped), "id": row_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    item = _row(row)
    item["conversions"] = [
        _row(r)
        for r in connection.execute(
            text(CONVERSION_SQL + " AND item_id=:id ORDER BY from_unit"),
            {**_s(scoped), "id": row_id},
        ).mappings()
    ]
    return item


def list_items(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        conversions: dict[int, list[dict[str, Any]]] = {}
        for r in connection.execute(
            text(CONVERSION_SQL + " ORDER BY from_unit"), _s(scoped)
        ).mappings():
            conversions.setdefault(r["item_id"], []).append(_row(r))
        return [
            {**_row(r), "conversions": conversions.get(r["id"], [])}
            for r in connection.execute(
                text(ITEM_SQL + " ORDER BY i.item_code"), _s(scoped)
            ).mappings()
        ]


def _insert_item(connection, scoped, values: dict) -> int:
    if connection.execute(
        text(f"SELECT 1 FROM wms.item WHERE {_S} AND item_code=:c"),
        {**_s(scoped), "c": values["item_code"]},
    ).first():
        raise _fields({"itemCode": "이미 등록된 품목 코드입니다."})
    _validate_item_rules(values)
    lot_tracked = values.get("lot_tracked", values.get("item_class") == "FG")
    return connection.execute(
        text(
            "INSERT INTO wms.item(workspace_id, generation_id, item_code, name, base_unit, item_class, "
            "lot_tracked, shelf_life_days, storage_condition, safety_stock, max_stock, abc_class, "
            "plm_part_no, plm_revision) "
            "VALUES (:w, :g, :item_code, :name, :base_unit, :item_class, :lot_tracked, "
            ":shelf_life_days, :storage_condition, :safety_stock, :max_stock, :abc_class, "
            ":plm_part_no, :plm_revision) RETURNING id"
        ),
        {
            **_s(scoped),
            "item_code": values["item_code"],
            "name": values["name"],
            "base_unit": values["base_unit"],
            "item_class": values["item_class"],
            "lot_tracked": lot_tracked,
            "shelf_life_days": values.get("shelf_life_days"),
            "storage_condition": values.get("storage_condition"),
            "safety_stock": values.get("safety_stock"),
            "max_stock": values.get("max_stock"),
            "abc_class": values.get("abc_class"),
            "plm_part_no": values.get("plm_part_no"),
            "plm_revision": values.get("plm_revision"),
        },
    ).scalar_one()


def create_item(context: AuthContext, values: dict, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        row_id = _insert_item(connection, scoped, values)
        return _item(connection, scoped, row_id), "item", row_id

    return _action(context, "wms.item.create", key, values, fn, 201)


def update_item(
    context: AuthContext, row_id: int, values: dict, key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def fn(connection, scoped):
        current = _item(connection, scoped, row_id)
        if current is None:
            raise _not_found("품목")
        if values.get("is_active") is False:
            from fs.wms.receiving import guard_master

            guard_master(connection, scoped, "item", row_id)
        merged = {**current, **values}
        _validate_item_rules(merged)
        sets = ", ".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE wms.item SET {sets} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": row_id},
        )
        return _item(connection, scoped, row_id), "item", row_id

    return _action(context, f"wms.item.update:{row_id}", key, values, fn)


MES_CLASS = {"raw": "RAW", "finished": "FG"}


def mes_item_candidates(context: AuthContext) -> list[dict[str, Any]]:
    """MES 품목 중 WMS에 없는 원자재·완제품. 반제품은 공정 내부라 제외한다(12장)."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = mes.items(connection, scoped, None)
        if rows is None:
            raise _source_off("mes")
        have = set(
            connection.execute(
                text(f"SELECT item_code FROM wms.item WHERE {_S}"), _s(scoped)
            ).scalars()
        )
        return [
            {**r, "itemClass": MES_CLASS[r["itemType"]]}
            for r in rows
            if r["itemType"] in MES_CLASS and r["itemCode"] not in have
        ]


def import_items(
    context: AuthContext, codes: list[str], key: str
) -> list[dict[str, Any]]:
    def fn(connection, scoped):
        rows = mes.items(connection, scoped, None)
        if rows is None:
            raise _source_off("mes")
        by_code = {r["itemCode"]: r for r in rows if r["itemType"] in MES_CLASS}
        missing = [c for c in codes if c not in by_code]
        if missing:
            raise _fields(
                {"itemCodes": f"가져올 수 없는 품목입니다: {', '.join(missing)}"}
            )
        ids = [
            _insert_item(
                connection,
                scoped,
                {
                    "item_code": c,
                    "name": by_code[c]["name"],
                    "base_unit": by_code[c]["baseUnit"],
                    "item_class": MES_CLASS[by_code[c]["itemType"]],
                },
            )
            for c in codes
        ]
        return [_item(connection, scoped, i) for i in ids], "item", ids[0]

    return _action(context, "wms.item.import", key, {"itemCodes": codes}, fn, 201)


def add_conversion(context: AuthContext, item_id: int, values: dict, key: str) -> dict:
    def fn(connection, scoped):
        item = _item(connection, scoped, item_id)
        if item is None:
            raise _not_found("품목")
        if values["from_unit"] == item["baseUnit"]:
            raise _fields({"fromUnit": "기본 단위와 다른 단위만 환산할 수 있습니다."})
        if any(c["fromUnit"] == values["from_unit"] for c in item["conversions"]):
            raise _fields({"fromUnit": "이미 환산이 있는 단위입니다."})
        factor = Decimal(values["factor"])
        if factor <= 0:
            raise _fields({"factor": "0보다 커야 합니다."})
        connection.execute(
            text(
                "INSERT INTO wms.item_unit_conversion(workspace_id,generation_id,item_id,from_unit,factor) "
                "VALUES (:w,:g,:i,:u,:f)"
            ),
            {**_s(scoped), "i": item_id, "u": values["from_unit"], "f": factor},
        )
        return _item(connection, scoped, item_id), "item", item_id

    return _action(context, f"wms.conversion.create:{item_id}", key, values, fn, 201)


def delete_conversion(
    context: AuthContext, item_id: int, conversion_id: int, key: str
) -> dict:
    def fn(connection, scoped):
        deleted = connection.execute(
            text(
                f"DELETE FROM wms.item_unit_conversion WHERE {_S} AND id=:id AND item_id=:i"
            ),
            {**_s(scoped), "id": conversion_id, "i": item_id},
        ).rowcount
        if not deleted:
            raise _not_found("단위 환산")
        return _item(connection, scoped, item_id), "item", item_id

    return _action(context, f"wms.conversion.delete:{conversion_id}", key, {}, fn)


# ---------- 원천 반영 (W-03, TX-W1·W3) ----------


def _source_off(module: str) -> ApiError:
    label = module.upper()
    return _conflict(
        f"{label}를 사용하지 않도록 설정했습니다. 수동 전표로 재고를 관리할 수 있습니다.",
        "SOURCE_MODULE_DISABLED",
        sourceModule=module,
    )


class Blocked(Exception):
    """반영할 수 없는 원천. reason은 화면 사유 코드."""

    def __init__(self, reason: str, **details: Any):
        super().__init__(reason)
        self.reason = reason
        self.details = details


def _sources(connection, scoped, kind: str) -> list[dict[str, Any]] | None:
    """원천 목록을 공통 모양 `{sourceKey, sourceRef, occurredAt, cancelledAt?, lines}`로. 원천 솔루션 꺼짐이면 None."""
    if kind == "MES_RECEIPT":
        rows = mes.finished_goods_receipts(connection, scoped)
        return (
            None
            if rows is None
            else [
                {
                    "sourceKey": f"MES:RECEIPT:{r['packingNo']}",
                    "sourceRef": r["packingNo"],
                    "occurredAt": r["receivedAt"],
                    "lines": r["lines"],
                }
                for r in rows
            ]
        )
    if kind == "MES_ISSUE":
        rows = mes.completed_material_issues(connection, scoped)
        return (
            None
            if rows is None
            else [
                {
                    "sourceKey": f"MES:ISSUE:{r['sourceRef']}",
                    "sourceRef": r["sourceRef"],
                    "occurredAt": r["endedAt"],
                    "lines": r["lines"],
                }
                for r in rows
            ]
        )
    if kind == "ERP_SHIPMENT":
        rows = erp.confirmed_shipments(connection, scoped)
        return (
            None
            if rows is None
            else [
                {
                    "sourceKey": f"ERP:SHIPMENT:{r['shipmentNo']}",
                    "sourceRef": r["shipmentNo"],
                    "occurredAt": r["shippedAt"],
                    "lines": r["lines"],
                }
                for r in rows
            ]
        )
    rows = erp.purchase_receipts(connection, scoped)
    return (
        None
        if rows is None
        else [
            {
                "sourceKey": f"ERP:PURCHASE:{r['invoiceNo']}",
                "sourceRef": r["invoiceNo"],
                "occurredAt": r["confirmedAt"],
                "cancelledAt": r["cancelledAt"],
                "lines": r["lines"],
            }
            for r in rows
        ]
    )


def _default_location(connection, scoped, purpose: str) -> int:
    location = connection.execute(
        text(
            "SELECT l.id FROM wms.storage_location l JOIN wms.warehouse h "
            "ON h.workspace_id=l.workspace_id AND h.generation_id=l.generation_id AND h.id=l.warehouse_id "
            "WHERE l.workspace_id=:w AND l.generation_id=:g AND h.purpose=:p AND h.is_active AND l.is_default"
        ),
        {**_s(scoped), "p": purpose},
    ).scalar()
    if location is None:
        raise Blocked("NO_WAREHOUSE", purpose=purpose)
    return location


def _items_by_code(connection, scoped) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for r in connection.execute(
        text(f"SELECT id, item_code, base_unit, item_class FROM wms.item WHERE {_S}"),
        _s(scoped),
    ).mappings():
        items[r["item_code"]] = {**r, "factors": {}}
    by_id = {v["id"]: v for v in items.values()}
    for r in connection.execute(text(CONVERSION_SQL), _s(scoped)).mappings():
        by_id[r["item_id"]]["factors"][r["from_unit"]] = r["factor"]
    return items


def _base_qty(item: dict[str, Any], qty: str, unit: str) -> Decimal:
    value = Decimal(qty)
    if unit == item["base_unit"]:
        return value.quantize(Q3)
    factor = item["factors"].get(unit)
    if factor is None:
        raise Blocked("UNIT_CONVERSION_MISSING", itemCode=item["item_code"], unit=unit)
    return (value * factor).quantize(Q3)


def _receipt_lots(
    connection, scoped, packing_no: str, item_id: int
) -> list[dict[str, Any]]:
    """반영된 MES 입고 전표에서 그 팔레트의 품목 LOT별 수량과 위치(출하 LOT 결정, 3장)."""
    return [
        dict(r)
        for r in connection.execute(
            text(
                "SELECT m.lot_no, m.location_id, m.qty_delta qty FROM wms.stock_move m "
                "JOIN wms.stock_document d ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id "
                "AND d.id=m.document_id "
                "WHERE m.workspace_id=:w AND m.generation_id=:g AND d.document_type='MES_RECEIPT' "
                "AND d.source_ref=:ref AND d.status='posted' AND m.item_id=:item ORDER BY m.line_no"
            ),
            {**_s(scoped), "ref": packing_no, "item": item_id},
        ).mappings()
    ]


def _plan(
    connection, scoped, kind: str, source: dict[str, Any]
) -> list[dict[str, Any]]:
    """원천 1건을 이동 줄로 바꾼다. 반영할 수 없으면 Blocked."""
    items = _items_by_code(connection, scoped)
    purpose = "FG" if kind in ("MES_RECEIPT", "ERP_SHIPMENT") else "RAW"
    location = _default_location(connection, scoped, purpose)
    sign = -1 if kind in ("MES_ISSUE", "ERP_SHIPMENT") else 1
    moves: list[dict[str, Any]] = []
    for line in source["lines"]:
        item = items.get(line["itemCode"])
        if item is None:
            raise Blocked("ITEM_NOT_REGISTERED", itemCode=line["itemCode"])
        qty = _base_qty(item, line["qty"], line["unit"])
        base = {
            "item_id": item["id"],
            "source_qty": Decimal(line["qty"]),
            "source_unit": line["unit"],
            "location_id": location,
            "lot_no": None,
        }
        if kind == "MES_RECEIPT" and item["item_class"] == "FG":
            base["lot_no"] = line.get("lotNo")
        if kind == "ERP_SHIPMENT" and line.get("packingNo"):
            lots = _receipt_lots(connection, scoped, line["packingNo"], item["id"])
            # ponytail: 팔레트 전량 출하만 LOT별로 나눈다. 부분 출하·수량 불일치는 LOT 미지정으로 차감한다.
            if lots and sum(x["qty"] for x in lots) == qty:
                for x in lots:
                    moves.append(
                        {
                            **base,
                            "lot_no": x["lot_no"],
                            "location_id": x["location_id"],
                            "qty_delta": -x["qty"],
                            "source_qty": x["qty"],
                            "source_unit": item["base_unit"],
                        }
                    )
                continue
        moves.append({**base, "qty_delta": sign * qty})
    return moves


def _document_by_source(connection, scoped, source_key: str, reversal: bool = False):
    return (
        connection.execute(
            text(
                f"SELECT id, document_no FROM wms.stock_document WHERE {_S} AND source_key=:k "
                + (
                    "AND document_type='REVERSAL'"
                    if reversal
                    else "AND document_type<>'REVERSAL'"
                )
            ),
            {**_s(scoped), "k": source_key},
        )
        .mappings()
        .first()
    )


def _insert_document(
    connection,
    scoped,
    header: dict[str, Any],
    moves: list[dict[str, Any]],
    moved_at: str | None,
) -> int:
    on = header["document_on"]
    doc_id = connection.execute(
        text(
            "INSERT INTO wms.stock_document(workspace_id,generation_id,document_no,document_type,status,"
            "source_key,source_ref,reverses_document_id,reason_code,document_on,document_month,posted_at,note) "
            "VALUES (:w,:g,:no,:type,:status,:key,:ref,:rev,:reason,:on,:month,"
            + (
                "COALESCE(CAST(:posted_at AS timestamptz),clock_timestamp())"
                if header["status"] == "posted"
                else "NULL"
            )
            + ",:note) RETURNING id"
        ),
        {
            **_s(scoped),
            "no": _next_no(connection, scoped, on if header.get("posted_at") else None),
            "posted_at": header.get("posted_at"),
            "type": header["document_type"],
            "status": header["status"],
            "key": header.get("source_key"),
            "ref": header.get("source_ref"),
            "rev": header.get("reverses_document_id"),
            "reason": header.get("reason_code"),
            "on": on,
            "month": f"{on:%Y-%m}",
            "note": header.get("note"),
        },
    ).scalar_one()
    _insert_moves(connection, scoped, doc_id, moves, moved_at)
    return doc_id


def _insert_moves(
    connection, scoped, doc_id: int, moves: list[dict[str, Any]], moved_at: str | None
) -> None:
    for number, m in enumerate(moves, 1):
        connection.execute(
            text(
                "INSERT INTO wms.stock_move(workspace_id,generation_id,document_id,line_no,item_id,location_id,"
                "lot_no,qty_delta,source_qty,source_unit,moved_at) VALUES "
                "(:w,:g,:d,:n,:item,:loc,:lot,:qty,:sq,:su,COALESCE(CAST(:at AS timestamptz),clock_timestamp()))"
            ),
            {
                **_s(scoped),
                "d": doc_id,
                "n": number,
                "item": m["item_id"],
                "loc": m["location_id"],
                "lot": m["lot_no"],
                "qty": m["qty_delta"],
                "sq": m.get("source_qty"),
                "su": m.get("source_unit"),
                "at": moved_at,
            },
        )


def _sync_one(connection, scoped, kind: str, source: dict[str, Any]) -> dict[str, Any]:
    if kind == "ERP_PURCHASE":
        from fs.wms.receiving import route

        claimed = route(connection, scoped, source)
        if claimed:
            return claimed
    existing = _document_by_source(connection, scoped, source["sourceKey"])
    cancelled = source.get("cancelledAt")
    if existing is None:
        if cancelled:
            raise Blocked("SOURCE_CANCELLED")
        moves = _plan(connection, scoped, kind, source)
        doc_id = _insert_document(
            connection,
            scoped,
            {
                "document_type": kind,
                "status": "posted",
                "source_key": source["sourceKey"],
                "source_ref": source["sourceRef"],
                "document_on": _seoul_day(source["occurredAt"]),
            },
            moves,
            source["occurredAt"],
        )
        return {
            "sourceKey": source["sourceKey"],
            "documentId": doc_id,
            "state": "synced",
        }
    if not cancelled:
        return {
            "sourceKey": source["sourceKey"],
            "documentId": existing["id"],
            "state": "synced",
        }
    reversal = _document_by_source(connection, scoped, source["sourceKey"], True)
    if reversal is not None:
        return {
            "sourceKey": source["sourceKey"],
            "documentId": reversal["id"],
            "state": "reversed",
        }
    moves = [
        {**dict(m), "qty_delta": -m["qty_delta"]}
        for m in connection.execute(
            text(
                f"SELECT item_id, location_id, lot_no, qty_delta, source_qty, source_unit "
                f"FROM wms.stock_move WHERE {_S} AND document_id=:d ORDER BY line_no"
            ),
            {**_s(scoped), "d": existing["id"]},
        ).mappings()
    ]
    doc_id = _insert_document(
        connection,
        scoped,
        {
            "document_type": "REVERSAL",
            "status": "posted",
            "source_key": source["sourceKey"],
            "source_ref": source["sourceRef"],
            "reverses_document_id": existing["id"],
            "document_on": _seoul_day(cancelled),
            "note": "ERP 매입 취소 반영",
        },
        moves,
        cancelled,
    )
    return {"sourceKey": source["sourceKey"], "documentId": doc_id, "state": "reversed"}


def list_sources(context: AuthContext, kind: str, state: str | None) -> dict[str, Any]:
    """7.3 미반영 계산. 저장하지 않는다. 반영할 수 없는 원천은 사유를 붙인다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        sources = _sources(connection, scoped, kind)
        if sources is None:
            return {
                "kind": kind,
                "disabled": True,
                "sourceModule": SOURCE_MODULE[kind],
                "rows": [],
            }
        docs = {
            (r["source_key"], r["document_type"] == "REVERSAL"): r
            for r in connection.execute(
                text(
                    f"SELECT id, document_no, document_type, source_key FROM wms.stock_document "
                    f"WHERE {_S} AND source_key IS NOT NULL"
                ),
                _s(scoped),
            ).mappings()
        }
        rows = []
        for source in sources:
            key = source["sourceKey"]
            posted, reversed_ = docs.get((key, False)), docs.get((key, True))
            row = {
                **source,
                "state": "pending",
                "reason": None,
                "documentId": None,
                "documentNo": None,
            }
            if kind == "ERP_PURCHASE":
                from fs.wms.receiving import route

                claimed = route(connection, scoped, source)
                if claimed:
                    rows.append({**row, **claimed})
                    continue
            done = reversed_ or posted
            if done:
                row.update(documentId=done["id"], documentNo=done["document_no"])
            if source.get("cancelledAt"):
                row["state"] = (
                    "reversed"
                    if reversed_
                    else "cancel_pending"
                    if posted
                    else "cancelled"
                )
            elif posted:
                row["state"] = "synced"
            else:
                try:
                    _plan(connection, scoped, kind, source)
                except Blocked as blocked:
                    row.update(
                        state="blocked",
                        reason={"code": blocked.reason, **blocked.details},
                    )
            rows.append(row)
        pending = {"pending", "cancel_pending", "blocked", "inspection_pending"}
        if state == "pending":
            rows = [r for r in rows if r["state"] in pending]
        elif state == "synced":
            rows = [r for r in rows if r["state"] not in pending]
        return {"kind": kind, "disabled": False, "rows": rows}


def sync_sources(
    context: AuthContext, kind: str, keys: list[str], key: str
) -> dict[str, Any]:
    """원천마다 따로 커밋한다 — 한 건의 반영 불가가 다른 건을 막지 않게(6장)."""
    results = []
    for source_key in dict.fromkeys(keys):

        def fn(connection, scoped, source_key=source_key):
            sources = _sources(connection, scoped, kind)
            if sources is None:
                raise _source_off(SOURCE_MODULE[kind])
            source = next((s for s in sources if s["sourceKey"] == source_key), None)
            if source is None:
                raise Blocked("SOURCE_NOT_FOUND")
            result = _sync_one(connection, scoped, kind, source)
            if result.get("noticeId"):
                return result, "inbound_notice", result["noticeId"]
            return result, "stock_document", result["documentId"]

        try:
            results.append(
                _action(
                    context,
                    f"wms.sync:{source_key}",
                    key,
                    {"kind": kind, "sourceKey": source_key},
                    fn,
                )
            )
        except Blocked as blocked:
            results.append(
                {
                    "sourceKey": source_key,
                    "state": "blocked",
                    "reason": {"code": blocked.reason, **blocked.details},
                }
            )
    synced = sum(r["state"] in ("synced", "reversed") for r in results)
    return {
        "results": results,
        "synced": synced,
        "blocked": sum(r["state"] == "blocked" for r in results),
        "deferred": sum(r["state"] == "inspection_pending" for r in results),
        "inspected": sum(
            r["state"] in {"inspected", "inspected_cancelled"} for r in results
        ),
    }


# ---------- 재고 전표 (W-04, TX-W2) ----------

DOCUMENT_SQL = """
SELECT d.id, d.document_no, d.document_type, d.status, d.source_key, d.source_ref, d.reverses_document_id,
       r.document_no reverses_document_no, d.reason_code, d.document_on, d.document_month, d.posted_at, d.note,
       d.created_at,
       (SELECT count(*) FROM wms.stock_move m
         WHERE m.workspace_id=d.workspace_id AND m.generation_id=d.generation_id AND m.document_id=d.id) line_count
FROM wms.stock_document d
LEFT JOIN wms.stock_document r ON r.workspace_id=d.workspace_id AND r.generation_id=d.generation_id
 AND r.id=d.reverses_document_id
WHERE d.workspace_id=:w AND d.generation_id=:g
"""
MOVE_SQL = """
SELECT m.id, m.document_id, m.line_no, m.item_id, i.item_code, i.name item_name, i.item_class, m.location_id,
       l.code location_code, l.location_type, h.code warehouse_code, m.lot_no, m.qty_delta, i.base_unit unit,
       m.source_qty, m.source_unit, m.moved_at
FROM wms.stock_move m
JOIN wms.item i ON i.workspace_id=m.workspace_id AND i.generation_id=m.generation_id AND i.id=m.item_id
JOIN wms.storage_location l ON l.workspace_id=m.workspace_id AND l.generation_id=m.generation_id
 AND l.id=m.location_id
JOIN wms.warehouse h ON h.workspace_id=l.workspace_id AND h.generation_id=l.generation_id AND h.id=l.warehouse_id
WHERE m.workspace_id=:w AND m.generation_id=:g
"""


def _document(
    connection, scoped, doc_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM wms.stock_document WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": doc_id},
        )
    row = (
        connection.execute(
            text(DOCUMENT_SQL + " AND d.id=:id"), {**_s(scoped), "id": doc_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    doc = _row(row)
    doc["noticeId"] = connection.execute(
        text(f"SELECT id FROM wms.inbound_notice WHERE {_S} AND stock_document_id=:d"),
        {**_s(scoped), "d": doc_id},
    ).scalar_one_or_none()
    doc["moves"] = [
        _row(r)
        for r in connection.execute(
            text(MOVE_SQL + " AND m.document_id=:d ORDER BY m.line_no"),
            {**_s(scoped), "d": doc_id},
        ).mappings()
    ]
    return doc


def list_documents(
    context: AuthContext, filters: dict[str, Any]
) -> list[dict[str, Any]]:
    clauses, params = [], {}
    for column, value in (
        ("document_type", filters.get("type")),
        ("status", filters.get("status")),
        ("document_month", filters.get("month")),
    ):
        if value:
            clauses.append(f"d.{column}=:{column}")
            params[column] = value
    where = "".join(f" AND {c}" for c in clauses)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            _row(r)
            for r in connection.execute(
                text(DOCUMENT_SQL + where + " ORDER BY d.document_on DESC, d.id DESC"),
                {**_s(scoped), **params},
            ).mappings()
        ]


def get_document(context: AuthContext, doc_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        doc = _document(connection, scoped, doc_id)
        if doc is None:
            raise _not_found("재고 전표")
        return doc


def _manual_moves(
    connection, scoped, doc_type: str, lines: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """수동 전표 줄 검증 → 이동 줄. 이동(TRANSFER)은 한 줄 = 보낼 −·받을 + 한 쌍."""
    errors: dict[str, str] = {}
    items = {
        r["id"]: r
        for r in connection.execute(
            text(f"SELECT id, item_class, is_active FROM wms.item WHERE {_S}"),
            _s(scoped),
        ).mappings()
    }
    locations = {
        r["id"]: r
        for r in connection.execute(
            text(f"SELECT id, is_active FROM wms.storage_location WHERE {_S}"),
            _s(scoped),
        ).mappings()
    }
    moves: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        at = f"lines.{index}"
        item = items.get(line["item_id"])
        if item is None or not item["is_active"]:
            errors[f"{at}.itemId"] = "사용 중인 품목을 고르세요."
            continue
        lot = line.get("lot_no")
        if item["item_class"] == "RAW" and lot:
            errors[f"{at}.lotNo"] = "원자재는 LOT을 지정하지 않습니다."
        qty = _qty(line["qty"])
        if doc_type == "TRANSFER":
            source, target = line.get("from_location_id"), line.get("to_location_id")
            for field, loc in (("fromLocationId", source), ("toLocationId", target)):
                if loc not in locations or not locations[loc]["is_active"]:
                    errors[f"{at}.{field}"] = "사용 중인 위치를 고르세요."
            if source is not None and source == target:
                errors[f"{at}.toLocationId"] = "보낼 위치와 다른 위치를 고르세요."
            if item["item_class"] == "FG" and not lot:
                errors[f"{at}.lotNo"] = "완제품 이동은 LOT을 지정해야 합니다."
            if qty <= 0:
                errors[f"{at}.qty"] = "0보다 커야 합니다."
            moves += [
                {
                    "item_id": item["id"],
                    "location_id": source,
                    "lot_no": lot,
                    "qty_delta": -qty,
                },
                {
                    "item_id": item["id"],
                    "location_id": target,
                    "lot_no": lot,
                    "qty_delta": qty,
                },
            ]
            continue
        loc = line.get("location_id")
        if loc not in locations or not locations[loc]["is_active"]:
            errors[f"{at}.locationId"] = "사용 중인 위치를 고르세요."
        if qty == 0 or (doc_type == "OPENING" and qty < 0):
            errors[f"{at}.qty"] = (
                "0보다 커야 합니다."
                if doc_type == "OPENING"
                else "0이 아닌 증감을 입력하세요."
            )
        moves.append(
            {"item_id": item["id"], "location_id": loc, "lot_no": lot, "qty_delta": qty}
        )
    if errors:
        raise _fields(errors)
    return moves


def _header_errors(
    doc_type: str, reason: str | None, note: str | None
) -> dict[str, str]:
    errors = {}
    if doc_type == "ADJUSTMENT" and not reason:
        errors["reasonCode"] = "조정 사유를 고르세요."
    if doc_type != "ADJUSTMENT" and reason:
        errors["reasonCode"] = "조정 전표에만 사유를 둡니다."
    if reason == "OTHER" and not (note and note.strip()):
        errors["note"] = "기타 사유는 메모가 필요합니다."
    return errors


def create_document(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        doc_type = values["document_type"]
        errors = _header_errors(doc_type, values.get("reason_code"), values.get("note"))
        if errors:
            raise _fields(errors)
        moves = _manual_moves(connection, scoped, doc_type, values["lines"])
        on = values.get("document_on")
        doc_id = _insert_document(
            connection,
            scoped,
            {
                "document_type": doc_type,
                "status": "draft",
                "reason_code": values.get("reason_code"),
                "note": values.get("note"),
                "document_on": date.fromisoformat(on) if on else business_today(),
            },
            moves,
            None,
        )
        return _document(connection, scoped, doc_id), "stock_document", doc_id

    return _action(context, "wms.document.create", key, values, fn, 201)


def _draft(connection, scoped, doc_id: int) -> dict[str, Any]:
    doc = _document(connection, scoped, doc_id, lock=True)
    if doc is None:
        raise _not_found("재고 전표")
    if doc["status"] != "draft":
        raise _conflict(
            "확정한 전표는 바꿀 수 없습니다. 조정 전표로 바로잡으세요.",
            "POSTED_IMMUTABLE",
        )
    return doc


def update_document(
    context: AuthContext, doc_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def fn(connection, scoped):
        doc = _draft(connection, scoped, doc_id)
        reason = values.get("reason_code", doc["reasonCode"])
        note = values.get("note", doc["note"])
        errors = _header_errors(doc["documentType"], reason, note)
        if errors:
            raise _fields(errors)
        on = values.get("document_on")
        day = date.fromisoformat(on) if on else date.fromisoformat(doc["documentOn"])
        connection.execute(
            text(
                f"UPDATE wms.stock_document SET reason_code=:r, note=:n, document_on=:on, document_month=:m "
                f"WHERE {_S} AND id=:id"
            ),
            {
                **_s(scoped),
                "r": reason,
                "n": note,
                "on": day,
                "m": f"{day:%Y-%m}",
                "id": doc_id,
            },
        )
        if values.get("lines") is not None:
            moves = _manual_moves(
                connection, scoped, doc["documentType"], values["lines"]
            )
            connection.execute(
                text(f"DELETE FROM wms.stock_move WHERE {_S} AND document_id=:d"),
                {**_s(scoped), "d": doc_id},
            )
            _insert_moves(connection, scoped, doc_id, moves, None)
        return _document(connection, scoped, doc_id), "stock_document", doc_id

    return _action(context, f"wms.document.update:{doc_id}", key, values, fn)


def delete_document(context: AuthContext, doc_id: int, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        _draft(connection, scoped, doc_id)
        connection.execute(
            text(f"DELETE FROM wms.stock_move WHERE {_S} AND document_id=:d"),
            {**_s(scoped), "d": doc_id},
        )
        connection.execute(
            text(f"DELETE FROM wms.stock_document WHERE {_S} AND id=:d"),
            {**_s(scoped), "d": doc_id},
        )
        return {"id": doc_id, "deleted": True}, "stock_document", doc_id

    return _action(context, f"wms.document.delete:{doc_id}", key, {}, fn)


def post_document(context: AuthContext, doc_id: int, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        doc = _draft(connection, scoped, doc_id)
        if not doc["moves"]:
            raise _conflict("줄이 없는 전표는 확정할 수 없습니다.", "NO_LINES")
        if doc["documentType"] == "TRANSFER":
            totals: dict[tuple[int, str | None], Decimal] = {}
            for m in doc["moves"]:
                k = (m["itemId"], m["lotNo"])
                totals[k] = totals.get(k, Decimal(0)) + Decimal(m["qtyDelta"])
            if any(v != 0 for v in totals.values()):
                raise _conflict(
                    "이동 전표는 품목·LOT별 합이 0이어야 합니다.", "TRANSFER_UNBALANCED"
                )
        connection.execute(
            text(
                f"UPDATE wms.stock_document SET status='posted', posted_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": doc_id},
        )
        connection.execute(
            text(
                f"UPDATE wms.stock_move SET moved_at=clock_timestamp() WHERE {_S} AND document_id=:d"
            ),
            {**_s(scoped), "d": doc_id},
        )
        posted = _document(connection, scoped, doc_id)
        posted["negative"] = _negatives(connection, scoped, doc_id)
        return posted, "stock_document", doc_id

    return _action(context, f"wms.document.post:{doc_id}", key, {}, fn)


# ---------- 재고 현황·원장 (W-02·W-05) ----------

STOCK_SQL = """
SELECT m.item_id, i.item_code, i.name item_name, i.item_class, i.base_unit unit, m.location_id,
       l.code location_code, h.id warehouse_id, h.code warehouse_code, m.lot_no, sum(m.qty_delta) on_hand
FROM wms.stock_move m
JOIN wms.stock_document d ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id
 AND d.id=m.document_id AND d.status='posted'
JOIN wms.item i ON i.workspace_id=m.workspace_id AND i.generation_id=m.generation_id AND i.id=m.item_id
JOIN wms.storage_location l ON l.workspace_id=m.workspace_id AND l.generation_id=m.generation_id
 AND l.id=m.location_id
JOIN wms.warehouse h ON h.workspace_id=l.workspace_id AND h.generation_id=l.generation_id AND h.id=l.warehouse_id
WHERE m.workspace_id=:w AND m.generation_id=:g
"""
STOCK_GROUP = " GROUP BY m.item_id, i.item_code, i.name, i.item_class, i.base_unit, m.location_id, l.code, h.id, h.code, m.lot_no"


def _negatives(connection, scoped, doc_id: int) -> list[dict[str, Any]]:
    """전표가 건드린 품목·위치·LOT 중 확정 후 음수가 된 것(D15 안내)."""
    rows = connection.execute(
        text(
            STOCK_SQL
            + " AND (m.item_id, m.location_id, coalesce(m.lot_no,'')) IN (SELECT item_id, location_id, coalesce(lot_no,'') "
            "FROM wms.stock_move WHERE workspace_id=:w AND generation_id=:g AND document_id=:d)"
            + STOCK_GROUP
            + " HAVING sum(m.qty_delta) < 0"
        ),
        {**_s(scoped), "d": doc_id},
    ).mappings()
    return [_row(r) for r in rows]


def stock(context: AuthContext, filters: dict[str, Any]) -> dict[str, Any]:
    from fs.wms import inventory

    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = inventory.rows(connection, scoped, filters)
        return {"rows": rows, "totals": inventory.totals(connection, scoped, rows)}


def moves(context: AuthContext, filters: dict[str, Any]) -> list[dict[str, Any]]:
    clauses, params = ["d.status='posted'"], {}
    for key, clause in (
        ("itemCode", "i.item_code=:itemCode"),
        ("lotNo", "m.lot_no=:lotNo"),
        ("warehouseId", "h.id=:warehouseId"),
        ("type", "d.document_type=:type"),
        ("from", "d.document_on>=:from"),
        ("to", "d.document_on<=:to"),
    ):
        if filters.get(key):
            clauses.append(clause)
            params[key] = filters[key]
    running = bool(filters.get("itemCode"))
    sql = (
        MOVE_SQL.replace(
            "m.moved_at\nFROM wms.stock_move m",
            "m.moved_at, d.document_no, d.document_type, d.source_ref"
            + (
                ", sum(m.qty_delta) OVER (PARTITION BY m.item_id, m.lot_no ORDER BY m.moved_at, m.id) running"
                if running
                else ""
            )
            + "\nFROM wms.stock_move m\nJOIN wms.stock_document d ON d.workspace_id=m.workspace_id "
            "AND d.generation_id=m.generation_id AND d.id=m.document_id",
        )
        + "".join(f" AND {c}" for c in clauses)
        + " ORDER BY m.moved_at, m.id"
    )
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        # ponytail: 전체 원장을 한 번에 돌려준다. 행이 수천을 넘으면 페이지 나눔을 붙인다.
        return [
            _row(r)
            for r in connection.execute(text(sql), {**_s(scoped), **params}).mappings()
        ]


# ---------- 대시보드 (W-01) ----------


def dashboard(context: AuthContext, month: str | None) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        month = (
            month
            or connection.execute(
                text(
                    f"SELECT max(document_month) FROM wms.stock_document WHERE {_S} AND status='posted'"
                ),
                _s(scoped),
            ).scalar()
            or f"{business_today():%Y-%m}"
        )
        from fs.wms import inventory

        rows = inventory.rows(connection, scoped)
        items = {
            row["itemCode"]: row for row in inventory.totals(connection, scoped, rows)
        }
        pending_by_kind: dict[str, int | None] = {}
        for kind in SOURCE_KINDS:
            sources = _sources(connection, scoped, kind)
            if sources is None:
                pending_by_kind[kind] = None
                continue
            keys = set(
                connection.execute(
                    text(
                        f"SELECT source_key FROM wms.stock_document WHERE {_S} AND source_key IS NOT NULL AND document_type<>'REVERSAL'"
                    ),
                    _s(scoped),
                ).scalars()
            )
            reversed_keys = set(
                connection.execute(
                    text(
                        f"SELECT source_key FROM wms.stock_document WHERE {_S} AND document_type='REVERSAL'"
                    ),
                    _s(scoped),
                ).scalars()
            )
            if kind == "ERP_PURCHASE":
                from fs.wms.receiving import route

                claimed_routes = {
                    s["sourceKey"]: route(connection, scoped, s) for s in sources
                }
            else:
                claimed_routes = {}
            pending_by_kind[kind] = sum(
                claimed_routes[s["sourceKey"]]["state"] == "inspection_pending"
                if claimed_routes.get(s["sourceKey"])
                else (s["sourceKey"] not in keys)
                if not s.get("cancelledAt")
                else (s["sourceKey"] in keys and s["sourceKey"] not in reversed_keys)
                for s in sources
            )
        flows = [
            _row(r)
            for r in connection.execute(
                text(
                    "SELECT i.item_code, sum(CASE WHEN m.qty_delta>0 THEN m.qty_delta ELSE 0 END) inbound, "
                    "sum(CASE WHEN m.qty_delta<0 THEN -m.qty_delta ELSE 0 END) outbound, i.base_unit unit "
                    "FROM wms.stock_move m JOIN wms.stock_document d ON d.workspace_id=m.workspace_id "
                    "AND d.generation_id=m.generation_id AND d.id=m.document_id AND d.status='posted' "
                    "AND d.document_type<>'TRANSFER' "
                    "JOIN wms.item i ON i.workspace_id=m.workspace_id AND i.generation_id=m.generation_id AND i.id=m.item_id "
                    "WHERE m.workspace_id=:w AND m.generation_id=:g AND d.document_month=:month "
                    "GROUP BY i.item_code, i.base_unit ORDER BY i.item_code"
                ),
                {**_s(scoped), "month": month},
            ).mappings()
        ]
        inbound_counts = dict(
            connection.execute(
                text(
                    f"SELECT status,count(*) FROM wms.inbound_notice WHERE {_S} GROUP BY status"
                ),
                _s(scoped),
            ).all()
        )
        known = [v for v in pending_by_kind.values() if v is not None]
        return {
            "month": month,
            "rawItems": sum(1 for e in items.values() if e["itemClass"] == "RAW"),
            "fgLots": sum(
                1
                for r in rows
                if r["itemClass"] == "FG" and r["lotNo"] and Decimal(r["onHand"]) > 0
            ),
            "negativeCount": sum(1 for r in rows if r["negative"]),
            "pendingSources": sum(known) if known else None,
            "pendingByKind": pending_by_kind,
            "inboundPlanned": inbound_counts.get("PLANNED", 0),
            "inboundArrived": inbound_counts.get("ARRIVED", 0),
            "shortageKeys": sum(
                1 for r in rows if Decimal(r["reservationShortage"]) > 0
            ),
            "items": sorted(items.values(), key=lambda e: e["itemCode"]),
            "flows": flows,
        }
