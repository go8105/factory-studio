"""CMMS 업무 규칙 (FS-029 모듈 설계 · DSN-21).

설계 전제(FS-029 D45~D52 · DSN-21 Q1~Q7):
- 설비 대장은 **직접 등록**과 **가져오기**(MES 설비·MES 금형·BEMS 공조기)로 채운다.
  가져온 설비는 원천 코드 1건당 1행이고(UK_PARTIAL), 원천 쪽은 바꾸지 않는다 — 읽기만 한다.
- 설비는 계층을 가질 수 있다(라인 > 설비 > 구성품). 자기 자신·후손을 상위로 둘 수 없다.
- 고장 코드는 증상·원인·조치 3종이고, 원인 코드만 보전 원인 6분류(마모·윤활·전기·설정·외부·기타)를 갖는다.
- 재고·비용은 저장하지 않는다(D50 · Q5) — 볼 때마다 WMS·계산으로 구한다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from fs.bems import interface as bems
from fs.common import master
from fs.common.auth import AuthContext
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.mes import interface as mes

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
