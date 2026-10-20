"""CMMS 업무 규칙 (FS-029 모듈 설계 · DSN-21).

설계 전제(FS-029 D45~D52 · DSN-21 Q1~Q7):
- 설비 대장은 **직접 등록**과 **가져오기**(MES 설비·MES 금형·BEMS 공조기)로 채운다.
  가져온 설비는 원천 코드 1건당 1행이고(UK_PARTIAL), 원천 쪽은 바꾸지 않는다 — 읽기만 한다.
- 설비는 계층을 가질 수 있다(라인 > 설비 > 구성품). 자기 자신·후손을 상위로 둘 수 없다.
- 고장 코드는 증상·원인·조치 3종이고, 원인 코드만 보전 원인 6분류(마모·윤활·전기·설정·외부·기타)를 갖는다.
- 재고·비용은 저장하지 않는다(D50 · Q5) — 볼 때마다 WMS·계산으로 구한다.
"""

from __future__ import annotations

from datetime import datetime
from functools import partial
from typing import Any

from sqlalchemy import text

from fs.bems import interface as bems
from fs.common import master
from fs.common.auth import AuthContext
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.erp import interface as erp
from fs.hr import interface as hr
from fs.mes import interface as mes
from fs.spc import interface as spc

MODULE = "cmms"
_S = "workspace_id=:w AND generation_id=:g"
# 가져오기 출처 → (설비 종류, 사람이 읽을 이름). 종류가 고정이라 CHECK와 어긋나지 않는다.
IMPORTS = {
    "MES": ("설비", None),
    "MES_MOLD": ("금형", "MOLD"),
    "BEMS": ("공조기", "HVAC"),
}


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _fields(fields: dict[str, str]) -> ApiError:
    return ApiError(
        400, "VALIDATION_FAILED", "입력을 확인해 주세요.", {"fields": fields}
    )


def _conflict(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


def _not_found(label: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{label}을(를) 찾을 수 없습니다.")


def _one(connection, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    row = connection.execute(text(sql), params).mappings().first()
    return None if row is None else master.present(row)


def _all(connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [master.present(r) for r in connection.execute(text(sql), params).mappings()]


def _now(connection) -> datetime:
    return connection.execute(text("SELECT clock_timestamp()")).scalar_one()


# 공통 엔진(fs.common.engine.action): 공간 잠금 → 멱등 영수증 → 처리 → 영수증 저장
_action = partial(action, MODULE)


def _source_disabled(module: str) -> ApiError:
    return ApiError(
        409,
        "PRECONDITION_NOT_MET",
        f"{module.upper()}를 사용하지 않도록 설정했습니다. 설비를 직접 등록할 수는 있습니다.",
        {"reason": "SOURCE_MODULE_DISABLED", "sourceModule": module},
    )


# ---------- 설비 대장 (C-05) ----------

ASSET = master.Master(
    module=MODULE,
    table="cmms.asset",
    columns=(
        "code",
        "name",
        "asset_type",
        "location",
        "source",
        "source_code",
        "parent_asset_id",
        "manufacturer",
        "model",
        "serial_no",
        "installed_on",
        "acquisition_cost",
        "criticality",
        "is_active",
    ),
    sort={"code": "code", "name": "name", "criticality": "criticality"},
    default_sort="code ASC",
    unique=("code",),
    filters={
        "assetType": "asset_type",
        "source": "source",
        "criticality": "criticality",
        "active": "is_active",
    },
    references=(
        master.Reference("cmms.asset", "parent_asset_id", "하위 설비"),
        master.Reference("cmms.work_order", "asset_id", "작업지시"),
        master.Reference("cmms.pm_plan", "asset_id", "예방보전 계획"),
        master.Reference("cmms.asset_part", "asset_id", "설비별 예비품"),
    ),
    not_found="설비를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 사용 중인 설비 코드입니다.",
    referenced_message=(
        "하위 설비·작업지시·보전 계획이 참조 중이라 삭제할 수 없습니다. "
        "사용 안 함으로 바꾸면 새 입력에서 제외됩니다."
    ),
)


def _descendants(connection, scoped, asset_id: int) -> set[int]:
    """자기 자신과 모든 후손. 상위를 고를 때 순환을 막는 데 쓴다."""
    rows = connection.execute(
        text(
            f"""
            WITH RECURSIVE tree AS (
              SELECT id FROM cmms.asset WHERE {_S} AND id=:id
              UNION ALL
              SELECT a.id FROM cmms.asset a JOIN tree t ON a.parent_asset_id=t.id
               WHERE a.workspace_id=:w AND a.generation_id=:g
            )
            SELECT id FROM tree
            """
        ),
        {**_s(scoped), "id": asset_id},
    ).scalars()
    return set(rows)


def _check_asset(connection, scoped, values, current, row_id):
    """계층 규칙: 상위는 같은 공간에 있어야 하고, 자기 자신이나 후손일 수 없다."""
    parent = values.get("parent_asset_id")
    if parent is None:
        return
    exists = connection.execute(
        text(f"SELECT 1 FROM cmms.asset WHERE {_S} AND id=:id"),
        {**_s(scoped), "id": parent},
    ).scalar()
    if exists is None:
        raise _fields({"parentAssetId": "상위 설비를 찾을 수 없습니다."})
    if row_id is not None and int(parent) in _descendants(connection, scoped, row_id):
        raise _fields(
            {"parentAssetId": "자기 자신이나 하위 설비를 상위로 둘 수 없습니다."}
        )


def assets(context: AuthContext, **kwargs) -> tuple[list[dict[str, Any]], int]:
    return master.listing(ASSET, context, **kwargs)


def asset(context: AuthContext, asset_id: int) -> dict[str, Any]:
    return master.detail(ASSET, context, asset_id)


def create_asset(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(
        ASSET, context, {**values, "source": "CMMS"}, key, check=_check_asset
    )


def update_asset(context: AuthContext, asset_id: int, values: dict[str, Any], key: str):
    return master.update(ASSET, context, asset_id, values, key, check=_check_asset)


def delete_asset(context: AuthContext, asset_id: int, key: str) -> None:
    master.delete(ASSET, context, asset_id, key)


def asset_tree(context: AuthContext) -> list[dict[str, Any]]:
    """대장을 계층 순서로 편다(상위 → 하위, 같은 층은 코드순). 화면은 depth만큼 들여 쓴다."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = [
            master.present(row)
            for row in connection.execute(
                text(
                    f"""
                    WITH RECURSIVE tree AS (
                      SELECT a.*, 0 depth, lpad(a.code, 24) path FROM cmms.asset a
                       WHERE a.{_S.replace(" AND ", " AND a.")} AND a.parent_asset_id IS NULL
                      UNION ALL
                      SELECT c.*, t.depth + 1, t.path || '>' || lpad(c.code, 24)
                        FROM cmms.asset c JOIN tree t ON c.parent_asset_id=t.id
                       WHERE c.workspace_id=:w AND c.generation_id=:g AND t.depth < 5
                    )
                    SELECT id, code, name, asset_type, location, source, source_code,
                           parent_asset_id, criticality, is_active, depth
                    FROM tree ORDER BY path
                    """
                ),
                _s(scoped),
            ).mappings()
        ]
        return rows


# ---------- 설비 가져오기 (C-05, FS-029 D46 · DSN-21 Q1) ----------


def _imported(connection, scoped, source: str) -> set[str]:
    return set(
        connection.execute(
            text(
                f"SELECT source_code FROM cmms.asset WHERE {_S} AND source=:source "
                "AND source_code IS NOT NULL"
            ),
            {**_s(scoped), "source": source},
        ).scalars()
    )


def _candidates(connection, scoped, source: str) -> list[dict[str, Any]]:
    """원천에서 읽어, 아직 대장에 없는 것만. 원천이 꺼져 있으면 409."""
    if source == "MES":
        rows = mes.equipment(connection, scoped)
        if rows is None:
            raise _source_disabled("mes")
        found = [
            {
                "sourceCode": r["equipmentCode"],
                "name": r["name"],
                "assetType": _MES_TYPE.get(r["equipmentType"], "OTHER"),
                "location": r["locationCode"],
            }
            for r in rows
        ]
    elif source == "MES_MOLD":
        rows = mes.molds(connection, scoped)
        if rows is None:
            raise _source_disabled("mes")
        found = [
            {
                "sourceCode": r["moldCode"],
                "name": r["name"],
                "assetType": "MOLD",
                "location": None,
                "note": f"{r['cavity']}캐비티 · 수명 {r['lifeShots']}타 · 누적 {r['shots']}타",
            }
            for r in rows
        ]
    else:
        rows = bems.hvac_units(connection, scoped)
        if rows is None:
            raise _source_disabled("bems")
        found = [
            {
                "sourceCode": r["code"],
                "name": r["name"],
                "assetType": "HVAC",
                "location": r["zoneName"],
            }
            for r in rows
        ]
    already = _imported(connection, scoped, source)
    return [f for f in found if f["sourceCode"] not in already]


# MES 설비 종류(약칭) → CMMS 설비 종류. 모르는 값은 OTHER로 둔다 —
# 원천이 종류를 늘려도 가져오기가 멈추지 않아야 하고, 사람이 대장에서 고쳐 줄 수 있다.
_MES_TYPE = {
    "INJ": "INJECTION",
    "ASM": "ASSEMBLY",
    "INS": "INSPECTION",
}


def import_candidates(context: AuthContext, source: str) -> list[dict[str, Any]]:
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _candidates(connection, scoped, source)


def import_assets(
    context: AuthContext, source: str, source_codes: list[str], key: str
) -> dict[str, Any]:
    """고른 원천 코드를 대장에 넣는다. 이미 있는 것은 조용히 건너뛴다(원천 1건당 1행).

    설비 코드는 원천 코드를 그대로 쓴다 — 두 쪽을 눈으로 맞출 수 있어야 하기 때문이다.
    코드 규칙에 맞지 않는 원천 코드는 건너뛰고 몇 건인지 알려 준다.
    """

    def fn(connection, scoped):
        found = {c["sourceCode"]: c for c in _candidates(connection, scoped, source)}
        used = set(
            connection.execute(
                text(f"SELECT code FROM cmms.asset WHERE {_S}"), _s(scoped)
            ).scalars()
        )
        created, skipped = [], []
        for code in source_codes:
            candidate = found.get(code)
            if candidate is None or code in used:
                skipped.append(code)
                continue
            new_id = connection.execute(
                text(
                    "INSERT INTO cmms.asset(workspace_id,generation_id,code,name,asset_type,"
                    "location,source,source_code) VALUES (:w,:g,:code,:name,:type,:loc,:source,:code) "
                    "RETURNING id"
                ),
                {
                    **_s(scoped),
                    "code": code,
                    "name": candidate["name"],
                    "type": candidate["assetType"],
                    "loc": candidate["location"],
                    "source": source,
                },
            ).scalar_one()
            created.append(new_id)
            used.add(code)
        return (
            {"created": len(created), "skipped": skipped, "ids": created},
            "asset",
            created[0] if created else 0,
        )

    return action(
        MODULE,
        context,
        f"cmms.asset.import:{source}",
        key,
        {"source": source, "codes": sorted(source_codes)},
        fn,
        201,
    )


# ---------- 작업지시 (C-03, FS-029 D47 · TX-C1~C5) ----------

WO_SQL = f"""
SELECT o.id, o.wo_no, o.asset_id, a.code asset_code, a.name asset_name, a.asset_type,
       o.kind, o.source, o.source_ref, o.source_summary, o.pm_plan_id, o.due_on,
       o.title, o.description, o.status, o.requested_at, o.failure_at, o.started_at,
       o.completed_at, o.restored_at, o.cause_category, o.action, o.cancelled_at,
       o.cancel_reason, o.technician_id, t.name technician_name, o.vendor_id,
       v.name vendor_name, o.external_cost, o.symptom_code_id, sc.code symptom_code,
       sc.name symptom_name, o.action_code_id, ac.code action_code, ac.name action_name
FROM cmms.work_order o
JOIN cmms.asset a ON a.workspace_id=o.workspace_id AND a.generation_id=o.generation_id
     AND a.id=o.asset_id
LEFT JOIN cmms.technician t ON t.workspace_id=o.workspace_id
     AND t.generation_id=o.generation_id AND t.id=o.technician_id
LEFT JOIN cmms.vendor v ON v.workspace_id=o.workspace_id
     AND v.generation_id=o.generation_id AND v.id=o.vendor_id
LEFT JOIN cmms.failure_code sc ON sc.workspace_id=o.workspace_id
     AND sc.generation_id=o.generation_id AND sc.id=o.symptom_code_id
LEFT JOIN cmms.failure_code ac ON ac.workspace_id=o.workspace_id
     AND ac.generation_id=o.generation_id AND ac.id=o.action_code_id
WHERE o.{_S.replace(" AND ", " AND o.")}
"""
OPEN_STATUSES = ("REQUESTED", "IN_PROGRESS")


def _work_order(connection, scoped, order_id: int, lock: bool = False):
    found = _one(
        connection,
        WO_SQL + " AND o.id=:id" + (" FOR UPDATE OF o" if lock else ""),
        {**_s(scoped), "id": order_id},
    )
    if found is None:
        raise _not_found("작업지시")
    return found


def _logs(connection, scoped, order_id: int) -> list[dict[str, Any]]:
    return _all(
        connection,
        "SELECT l.id, l.logged_at, l.minutes, l.note, l.technician_id, t.name technician_name "
        "FROM cmms.work_log l "
        "LEFT JOIN cmms.technician t ON t.workspace_id=l.workspace_id "
        " AND t.generation_id=l.generation_id AND t.id=l.technician_id "
        f"WHERE l.{_S.replace(' AND ', ' AND l.')} AND l.work_order_id=:id "
        "ORDER BY l.logged_at, l.id",
        {**_s(scoped), "id": order_id},
    )


def work_orders(
    context: AuthContext,
    status: str | None,
    kind: str | None,
    asset_id: int | None,
) -> list[dict[str, Any]]:
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            WO_SQL + " AND (CAST(:st AS text) IS NULL OR o.status=:st)"
            " AND (CAST(:kind AS text) IS NULL OR o.kind=:kind)"
            " AND (CAST(:asset AS bigint) IS NULL OR o.asset_id=:asset)"
            " ORDER BY o.requested_at DESC, o.id DESC LIMIT 500",
            {**_s(scoped), "st": status, "kind": kind, "asset": asset_id},
        )


def work_order(context: AuthContext, order_id: int) -> dict[str, Any]:
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _work_order(connection, scoped, order_id)
        return {**found, "logs": _logs(connection, scoped, order_id)}


def _next_wo_no(connection, scoped) -> str:
    """WO-0001 꼴. 세대 안에서만 이어지는 번호라 공간마다 1번부터 시작한다."""
    used = connection.execute(
        text(f"SELECT count(*) FROM cmms.work_order WHERE {_S}"), _s(scoped)
    ).scalar_one()
    return f"WO-{used + 1:04d}"


def _lock_asset(connection, scoped, asset_id: int) -> dict[str, Any]:
    found = _one(
        connection,
        f"SELECT id, code, name, is_active FROM cmms.asset WHERE {_S} AND id=:id FOR UPDATE",
        {**_s(scoped), "id": asset_id},
    )
    if found is None:
        raise _fields({"assetId": "설비를 찾을 수 없습니다."})
    if not found["isActive"]:
        raise _conflict("사용하지 않는 설비입니다.", "ASSET_INACTIVE")
    return found


def _code_of(connection, scoped, code_id: int | None, kind: str, field: str):
    """고장 코드가 그 구분이 맞는지 본다 — 증상 칸에 조치 코드를 넣는 실수를 막는다."""
    if code_id is None:
        return
    found = _one(
        connection,
        f"SELECT id, kind FROM cmms.failure_code WHERE {_S} AND id=:id",
        {**_s(scoped), "id": code_id},
    )
    if found is None or found["kind"] != kind:
        raise _fields({field: "그 구분의 고장 코드를 골라 주세요."})


def create_work_order(context: AuthContext, values: dict[str, Any], key: str):
    """직접 접수하는 고장 작업지시(BM). PM은 보전 계획에서, 신호 전환은 C-02에서 만든다."""

    def fn(connection, scoped):
        _lock_asset(connection, scoped, values["asset_id"])
        _code_of(
            connection,
            scoped,
            values.get("symptom_code_id"),
            "SYMPTOM",
            "symptomCodeId",
        )
        failure_at = values.get("failure_at") or _now(connection)
        new_id = connection.execute(
            text(
                "INSERT INTO cmms.work_order(workspace_id,generation_id,wo_no,asset_id,kind,"
                "source,title,description,status,requested_at,failure_at,technician_id,"
                "symptom_code_id) VALUES (:w,:g,:no,:asset,'BM','MANUAL',:title,:desc,"
                "'REQUESTED',clock_timestamp(),:failure,:tech,:symptom) RETURNING id"
            ),
            {
                **_s(scoped),
                "no": _next_wo_no(connection, scoped),
                "asset": values["asset_id"],
                "title": values["title"],
                "desc": values.get("description"),
                "failure": failure_at,
                "tech": values.get("technician_id"),
                "symptom": values.get("symptom_code_id"),
            },
        ).scalar_one()
        return _work_order(connection, scoped, new_id), "work_order", new_id

    body = {**values}
    if body.get("failure_at") is not None:
        body["failure_at"] = body["failure_at"].isoformat()
    return _action(context, "cmms.work_order.create", key, body, fn, 201)


def start_work_order(context: AuthContext, order_id: int, values: dict, key: str):
    """접수 → 진행(TX-C2). 담당 정비원을 여기서 정하거나 바꿀 수 있다."""

    def fn(connection, scoped):
        found = _work_order(connection, scoped, order_id, lock=True)
        if found["status"] != "REQUESTED":
            raise _conflict(
                "접수 상태의 작업지시만 시작할 수 있습니다.",
                "NOT_REQUESTED",
                status=found["status"],
            )
        connection.execute(
            text(
                "UPDATE cmms.work_order SET status='IN_PROGRESS', started_at=clock_timestamp(), "
                f"technician_id=COALESCE(:tech, technician_id) WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "tech": values.get("technician_id"), "id": order_id},
        )
        return _work_order(connection, scoped, order_id), "work_order", order_id

    return _action(context, f"cmms.work_order.start:{order_id}", key, values, fn)


def add_work_log(context: AuthContext, order_id: int, values: dict, key: str):
    """작업 기록은 진행 중일 때만 붙는다(TX-C3). 분 단위로 쌓아 인건비를 계산한다."""

    def fn(connection, scoped):
        found = _work_order(connection, scoped, order_id, lock=True)
        if found["status"] != "IN_PROGRESS":
            raise _conflict(
                "진행 중인 작업지시에만 작업 기록을 남길 수 있습니다.",
                "NOT_IN_PROGRESS",
                status=found["status"],
            )
        connection.execute(
            text(
                "INSERT INTO cmms.work_log(workspace_id,generation_id,work_order_id,"
                "logged_at,minutes,note,technician_id) "
                "VALUES (:w,:g,:id,clock_timestamp(),:minutes,:note,:tech)"
            ),
            {
                **_s(scoped),
                "id": order_id,
                "minutes": values["minutes"],
                "note": values.get("note"),
                "tech": values.get("technician_id") or found["technicianId"],
            },
        )
        return (
            {
                **_work_order(connection, scoped, order_id),
                "logs": _logs(connection, scoped, order_id),
            },
            "work_order",
            order_id,
        )

    return _action(context, f"cmms.work_order.log:{order_id}", key, values, fn, 201)


def complete_work_order(context: AuthContext, order_id: int, values: dict, key: str):
    """진행 → 완료(TX-C4). 원인·조치는 반드시 적고, 고장이면 복구 시각도 적는다.

    완료 뒤에는 바꿀 수 없다 — 지표(MTBF·MTTR)가 이 시각들로 계산되기 때문이다.
    """

    def fn(connection, scoped):
        found = _work_order(connection, scoped, order_id, lock=True)
        if found["status"] != "IN_PROGRESS":
            raise _conflict(
                "진행 중인 작업지시만 완료할 수 있습니다.",
                "NOT_IN_PROGRESS",
                status=found["status"],
            )
        _code_of(
            connection, scoped, values.get("action_code_id"), "ACTION", "actionCodeId"
        )
        restored_at = values.get("restored_at")
        if found["kind"] == "BM":
            restored_at = restored_at or _now(connection)
            if restored_at < datetime.fromisoformat(found["failureAt"]):
                raise _fields(
                    {"restoredAt": "복구 시각은 고장 시각보다 늦어야 합니다."}
                )
        elif restored_at is not None:
            raise _fields({"restoredAt": "예방보전에는 복구 시각을 적지 않습니다."})
        if values.get("external_cost") is not None and not (
            values.get("vendor_id") or found["vendorId"]
        ):
            raise _fields({"vendorId": "외주 비용을 적으려면 업체를 골라 주세요."})
        connection.execute(
            text(
                "UPDATE cmms.work_order SET status='COMPLETED', completed_at=clock_timestamp(), "
                "restored_at=:restored, cause_category=:cause, action=:action, "
                "action_code_id=:action_code, vendor_id=COALESCE(:vendor, vendor_id), "
                f"external_cost=:cost WHERE {_S} AND id=:id"
            ),
            {
                **_s(scoped),
                "restored": restored_at,
                "cause": values["cause_category"],
                "action": values["action"].strip(),
                "action_code": values.get("action_code_id"),
                "vendor": values.get("vendor_id"),
                "cost": values.get("external_cost"),
                "id": order_id,
            },
        )
        return _work_order(connection, scoped, order_id), "work_order", order_id

    body = {**values}
    if body.get("restored_at") is not None:
        body["restored_at"] = body["restored_at"].isoformat()
    return _action(context, f"cmms.work_order.complete:{order_id}", key, body, fn)


def cancel_work_order(context: AuthContext, order_id: int, reason: str, key: str):
    """접수·진행 → 취소(TX-C5). 취소하면 그 신호를 다시 전환할 수 있다(UK_PARTIAL이 취소를 뺀다)."""

    def fn(connection, scoped):
        found = _work_order(connection, scoped, order_id, lock=True)
        if found["status"] not in OPEN_STATUSES:
            raise _conflict(
                "접수·진행 중인 작업지시만 취소할 수 있습니다.",
                "NOT_OPEN",
                status=found["status"],
            )
        connection.execute(
            text(
                "UPDATE cmms.work_order SET status='CANCELLED', cancelled_at=clock_timestamp(), "
                f"cancel_reason=:reason WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "reason": reason.strip(), "id": order_id},
        )
        return _work_order(connection, scoped, order_id), "work_order", order_id

    return _action(
        context, f"cmms.work_order.cancel:{order_id}", key, {"reason": reason}, fn
    )


# ---------- 전환 대기 신호 (C-02, FS-029 D48) ----------


def _converted(connection, scoped) -> set[tuple[str, str]]:
    """이미 전환한 (출처, 원천 id). 취소한 것은 빠져서 다시 전환할 수 있다."""
    rows = connection.execute(
        text(
            f"SELECT source, source_ref FROM cmms.work_order WHERE {_S} "
            "AND source_ref IS NOT NULL AND status <> 'CANCELLED'"
        ),
        _s(scoped),
    )
    return {(r.source, r.source_ref) for r in rows}


def pending_signals(context: AuthContext) -> dict[str, Any]:
    """아직 작업지시가 되지 않은 BEMS 환경 경보·SPC 설비 이상.

    원천이 꺼져 있으면 그 줄만 비고 `sources`에 꺼짐으로 표시한다 — 전체가 막히지는 않는다.
    """
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        done = _converted(connection, scoped)
        alarms = bems.active_alarms(connection, scoped)
        signals = spc.equipment_signals(connection, scoped)
        # BEMS 경보는 구역 단위라 그 구역의 공조기 대장을 기본 설비로 고른다(13장 2).
        by_source_code = {
            (row["source"], row["sourceCode"]): row
            for row in _all(
                connection,
                f"SELECT id, code, name, source, source_code, location FROM cmms.asset "
                f"WHERE {_S} AND source_code IS NOT NULL AND is_active",
                _s(scoped),
            )
        }
        by_zone = {
            row["location"]: row
            for row in by_source_code.values()
            if row["source"] == "BEMS" and row["location"]
        }
        rows = []
        for alarm in alarms or []:
            if ("BEMS_ALARM", alarm["alarmId"]) in done:
                continue
            suggested = by_zone.get(alarm["zoneName"])
            rows.append(
                {
                    "id": f"BEMS_ALARM:{alarm['alarmId']}",
                    "source": "BEMS_ALARM",
                    "sourceRef": alarm["alarmId"],
                    "summary": (
                        f"{alarm['zoneName']} {alarm['metric']} "
                        f"{'상한' if alarm['comparator'] == 'HIGH' else '하한'} "
                        f"{alarm['threshold']} 초과(최고 {alarm['peakValue']})"
                    ),
                    "severity": alarm["severity"],
                    "detectedAt": alarm["raisedAt"],
                    "suggestedAssetId": suggested["id"] if suggested else None,
                    "suggestedAssetCode": suggested["code"] if suggested else None,
                }
            )
        for signal in signals or []:
            if ("SPC_SIGNAL", signal["signalId"]) in done:
                continue
            suggested = by_source_code.get(("MES", signal["equipmentCode"]))
            rows.append(
                {
                    "id": f"SPC_SIGNAL:{signal['signalId']}",
                    "source": "SPC_SIGNAL",
                    "sourceRef": signal["signalId"],
                    "summary": (
                        f"{signal['equipmentCode']} {signal['characteristicName']} "
                        f"규칙 {signal['rule']}({signal['chart']}) · LOT {signal['lotNo']}"
                    ),
                    "severity": None,
                    "detectedAt": signal["detectedAt"],
                    "suggestedAssetId": suggested["id"] if suggested else None,
                    "suggestedAssetCode": suggested["code"] if suggested else None,
                }
            )
        rows.sort(key=lambda r: r["detectedAt"], reverse=True)
        return {
            "sources": {
                "bems": alarms is not None,
                "spc": signals is not None,
            },
            "signals": rows,
        }


def convert_signal(context: AuthContext, values: dict[str, Any], key: str):
    """신호 하나를 고장 작업지시로 바꾼다. **원천 상태는 바꾸지 않는다**(D48).

    같은 신호로 취소되지 않은 작업지시는 1건뿐이다(UK_PARTIAL). 취소하면 다시 전환할 수 있다.
    """

    def fn(connection, scoped):
        source, source_ref = values["source"], values["source_ref"]
        _lock_asset(connection, scoped, values["asset_id"])
        if (source, source_ref) in _converted(connection, scoped):
            raise _conflict("이미 작업지시로 전환한 신호입니다.", "ALREADY_CONVERTED")
        new_id = connection.execute(
            text(
                "INSERT INTO cmms.work_order(workspace_id,generation_id,wo_no,asset_id,kind,"
                "source,source_ref,source_summary,title,status,requested_at,failure_at) "
                "VALUES (:w,:g,:no,:asset,'BM',:source,:ref,:summary,:title,'REQUESTED',"
                "clock_timestamp(),:failure) RETURNING id"
            ),
            {
                **_s(scoped),
                "no": _next_wo_no(connection, scoped),
                "asset": values["asset_id"],
                "source": source,
                "ref": source_ref,
                "summary": values["summary"],
                "title": values.get("title") or values["summary"][:200],
                "failure": values.get("detected_at") or _now(connection),
            },
        ).scalar_one()
        return _work_order(connection, scoped, new_id), "work_order", new_id

    body = {**values}
    if body.get("detected_at") is not None:
        body["detected_at"] = body["detected_at"].isoformat()
    return _action(
        context,
        f"cmms.signal.convert:{values['source']}:{values['source_ref']}",
        key,
        body,
        fn,
        201,
    )


# ---------- 정비원·외주 업체 (C-08, DSN-21 Q5) ----------

TECHNICIAN = master.Master(
    module=MODULE,
    table="cmms.technician",
    columns=(
        "code",
        "name",
        "skill",
        "hourly_rate",
        "currency",
        "hr_employee_code",
        "is_active",
    ),
    sort={"code": "code", "name": "name", "skill": "skill"},
    default_sort="code ASC",
    unique=("code",),
    filters={"skill": "skill", "active": "is_active"},
    references=(
        master.Reference("cmms.work_order", "technician_id", "작업지시"),
        master.Reference("cmms.work_log", "technician_id", "작업 기록"),
    ),
    not_found="정비원을 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 사용 중인 정비원 코드입니다.",
    referenced_message=(
        "작업지시·작업 기록이 참조 중이라 삭제할 수 없습니다. "
        "사용 안 함으로 바꾸면 새 입력에서 제외됩니다."
    ),
)
VENDOR = master.Master(
    module=MODULE,
    table="cmms.vendor",
    columns=("code", "name", "erp_partner_code", "phone", "is_active"),
    sort={"code": "code", "name": "name"},
    default_sort="code ASC",
    unique=("code",),
    filters={"active": "is_active"},
    references=(master.Reference("cmms.work_order", "vendor_id", "작업지시"),),
    not_found="외주 업체를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 사용 중인 업체 코드입니다.",
    referenced_message=(
        "작업지시가 참조 중이라 삭제할 수 없습니다. 사용 안 함으로 바꿔 주세요."
    ),
)


def technicians(context: AuthContext, **kwargs) -> tuple[list[dict[str, Any]], int]:
    return master.listing(TECHNICIAN, context, **kwargs)


def create_technician(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(TECHNICIAN, context, values, key)


def update_technician(context: AuthContext, row_id: int, values: dict, key: str):
    return master.update(TECHNICIAN, context, row_id, values, key)


def delete_technician(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(TECHNICIAN, context, row_id, key)


def vendors(context: AuthContext, **kwargs) -> tuple[list[dict[str, Any]], int]:
    return master.listing(VENDOR, context, **kwargs)


def create_vendor(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(VENDOR, context, values, key)


def update_vendor(context: AuthContext, row_id: int, values: dict, key: str):
    return master.update(VENDOR, context, row_id, values, key)


def delete_vendor(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(VENDOR, context, row_id, key)


def hr_employees(context: AuthContext) -> list[dict[str, Any]]:
    """정비원에 이어 붙일 HR 사원 목록. HR이 꺼져 있으면 빈 목록(코드를 손으로 적으면 된다)."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = hr.employees(connection, scoped)
        return found or []


def erp_partners(context: AuthContext) -> list[dict[str, Any]]:
    """외주 업체에 이어 붙일 ERP 매입처. ERP가 꺼져 있으면 빈 목록."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = erp.partners(connection, scoped, "SUPPLIER")
        return found or []


# ---------- 고장 코드 (C-09, F24) ----------

FAILURE_CODE = master.Master(
    module=MODULE,
    table="cmms.failure_code",
    columns=("kind", "code", "name", "cause_category", "is_active"),
    sort={"code": "code", "name": "name", "kind": "kind"},
    default_sort="kind ASC, code ASC",
    unique=("kind", "code"),
    filters={"kind": "kind", "active": "is_active"},
    references=(
        master.Reference("cmms.work_order", "symptom_code_id", "작업지시 증상"),
        master.Reference("cmms.work_order", "action_code_id", "작업지시 조치"),
    ),
    not_found="고장 코드를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="같은 구분에 이미 있는 코드입니다.",
    referenced_message="작업지시가 참조 중이라 삭제할 수 없습니다. 사용 안 함으로 바꿔 주세요.",
)


def _check_failure_code(connection, scoped, values, current, row_id):
    """원인 코드만 보전 원인 분류를 갖는다 — 증상·조치는 분류가 없다(DB CHECK와 같은 규칙).

    values는 수정이면 현재 행과 합친 값이라, 두 조건을 그대로 겹쳐 보면 된다.
    """
    if values.get("kind") == "CAUSE":
        if values.get("cause_category") is None:
            raise _fields({"causeCategory": "원인 코드는 원인 분류를 골라야 합니다."})
    elif values.get("cause_category") is not None:
        raise _fields(
            {"causeCategory": "증상·조치 코드에는 원인 분류를 두지 않습니다."}
        )


def failure_codes(context: AuthContext, **kwargs) -> tuple[list[dict[str, Any]], int]:
    return master.listing(FAILURE_CODE, context, **kwargs)


def create_failure_code(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(FAILURE_CODE, context, values, key, check=_check_failure_code)


def update_failure_code(
    context: AuthContext, code_id: int, values: dict[str, Any], key: str
):
    return master.update(
        FAILURE_CODE, context, code_id, values, key, check=_check_failure_code
    )


def delete_failure_code(context: AuthContext, code_id: int, key: str) -> None:
    master.delete(FAILURE_CODE, context, code_id, key)
