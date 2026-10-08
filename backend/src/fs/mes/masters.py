"""MES 보강 기준정보 (DSN-12 F06~F09·F18·F52).

불량·사유 코드, 근무조·작업자, 라벨 양식, 공정 검사 항목. 모두 공통 엔진(fs.common.master)을 쓴다.
기존 MES 화면(사업장·설비·품목…)은 자기 방식을 그대로 둔다 — 이 파일은 W2a 신규 기준정보만 맡는다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from fs.common import master
from fs.common.auth import AuthContext

MODULE = "mes"

DEFECT_CODE = master.Master(
    module=MODULE,
    table="mes.defect_code",
    columns=("code", "name", "category", "is_active"),
    sort={"code": "code", "name": "name"},
    default_sort="category ASC, code ASC",
    unique=("code",),
    filters={"category": "category", "isActive": "is_active"},
    references=(
        master.Reference(
            "mes.process_defect_code", "defect_code_id", "공정별 불량 코드"
        ),
        master.Reference("mes.operation_defect", "defect_code_id", "불량 명세"),
    ),
    not_found="불량 코드를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 있는 불량 코드입니다.",
    referenced_message="공정이나 실적이 쓰는 코드는 삭제할 수 없습니다. 사용 안 함으로 바꾸세요.",
)
REASON_CODE = master.Master(
    module=MODULE,
    table="mes.reason_code",
    columns=("category", "code", "name", "planned", "is_active"),
    sort={"code": "code", "name": "name"},
    default_sort="category ASC, code ASC",
    unique=("category", "code"),
    filters={"category": "category", "isActive": "is_active"},
    references=(
        master.Reference("mes.downtime", "reason_code_id", "비가동"),
        master.Reference("mes.material_adjustment", "reason_code_id", "비계획 입출고"),
    ),
    not_found="사유 코드를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="그 구분에 이미 있는 사유 코드입니다.",
    referenced_message="비가동이나 비계획 입출고가 쓰는 코드는 삭제할 수 없습니다.",
)
SHIFT = master.Master(
    module=MODULE,
    table="mes.shift",
    columns=("code", "name", "start_time", "end_time", "is_active"),
    sort={"code": "code", "name": "name"},
    default_sort="start_time ASC, code ASC",
    unique=("code",),
    filters={"isActive": "is_active"},
    references=(master.Reference("mes.worker", "shift_id", "작업자"),),
    not_found="근무조를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 있는 근무조 코드입니다.",
    referenced_message="작업자가 속한 근무조는 삭제할 수 없습니다.",
)
WORKER = master.Master(
    module=MODULE,
    table="mes.worker",
    columns=("code", "name", "shift_id", "hr_employee_code", "is_active"),
    sort={"code": "code", "name": "name"},
    default_sort="code ASC",
    unique=("code",),
    filters={"shiftId": "shift_id", "isActive": "is_active"},
    references=(master.Reference("mes.execution_worker", "worker_id", "실행 작업자"),),
    not_found="작업자를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 있는 작업자 코드입니다. 코드가 곧 작업자 바코드입니다.",
    referenced_message="공정 실행에 기록된 작업자는 삭제할 수 없습니다.",
)
LABEL_TEMPLATE = master.Master(
    module=MODULE,
    table="mes.label_template",
    columns=(
        "code",
        "label_kind",
        "barcode_type",
        "width_mm",
        "height_mm",
        "fields",
        "is_default",
        "is_active",
    ),
    sort={"code": "code", "labelKind": "label_kind"},
    default_sort="label_kind ASC, code ASC",
    unique=("code",),
    filters={"labelKind": "label_kind", "isActive": "is_active"},
    references=(master.Reference("mes.label_print", "template_id", "라벨 출력"),),
    not_found="라벨 양식을 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 있는 라벨 양식 코드입니다.",
    referenced_message="출력 기록이 있는 양식은 삭제할 수 없습니다.",
)
INSPECTION_ITEM = master.Master(
    module=MODULE,
    table="mes.inspection_item",
    columns=(
        "process_id",
        "item_id",
        "seq",
        "name",
        "method",
        "lower_limit",
        "upper_limit",
        "unit",
        "is_active",
    ),
    sort={"seq": "seq", "name": "name"},
    default_sort="process_id ASC, seq ASC",
    unique=("process_id", "item_id", "seq"),
    filters={"processId": "process_id", "itemId": "item_id", "isActive": "is_active"},
    references=(
        master.Reference(
            "mes.process_inspection_value", "inspection_item_id", "공정 검사 값"
        ),
    ),
    not_found="공정 검사 항목을 찾을 수 없습니다.",
    duplicate_field="seq",
    duplicate_message="그 공정·품목에 같은 순번이 이미 있습니다.",
    referenced_message="검사 값이 기록된 항목은 삭제할 수 없습니다.",
)


def _invalid(field: str, message: str):
    from fs.common.errors import ApiError

    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {master.camel(field): message}},
    )


def _exists(connection, scoped: AuthContext, table: str, row_id: int | None) -> bool:
    if row_id is None:
        return True
    return (
        connection.execute(
            text(
                f"SELECT 1 FROM {table} WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "id": row_id},
        ).first()
        is not None
    )


# ── 불량 코드 ────────────────────────────────────────────────────────────────


def defect_codes(context: AuthContext, **kwargs):
    return master.listing(DEFECT_CODE, context, **kwargs)


def create_defect_code(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(DEFECT_CODE, context, values, key)


def update_defect_code(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(DEFECT_CODE, context, row_id, values, key)


def delete_defect_code(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(DEFECT_CODE, context, row_id, key)


# ── 사유 코드 ────────────────────────────────────────────────────────────────


def reason_codes(context: AuthContext, **kwargs):
    return master.listing(REASON_CODE, context, **kwargs)


def create_reason_code(context: AuthContext, values: dict[str, Any], key: str):
    _check_reason(values)
    return master.create(REASON_CODE, context, values, key)


def update_reason_code(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    def check(_connection, _scoped, merged, _current, _row_id):
        _check_reason(merged)

    return master.update(REASON_CODE, context, row_id, values, key, check=check)


def delete_reason_code(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(REASON_CODE, context, row_id, key)


def _check_reason(values: dict[str, Any]) -> None:
    """'계획된 정지'는 비가동 사유에만 쓴다(DB CHECK와 같은 규칙)."""
    if values.get("planned") and values.get("category") != "DOWNTIME":
        raise _invalid("planned", "계획된 정지는 비가동 사유에만 표시합니다.")


# ── 근무조·작업자 ────────────────────────────────────────────────────────────


def shifts(context: AuthContext, **kwargs):
    return master.listing(SHIFT, context, **kwargs)


def create_shift(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(SHIFT, context, values, key)


def update_shift(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    return master.update(SHIFT, context, row_id, values, key)


def delete_shift(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(SHIFT, context, row_id, key)


def workers(context: AuthContext, **kwargs):
    return master.listing(WORKER, context, **kwargs)


def _check_worker(connection, scoped, merged, _current, _row_id):
    if not _exists(connection, scoped, "mes.shift", merged.get("shift_id")):
        raise _invalid("shift_id", "현재 공간의 근무조를 선택하세요.")


def create_worker(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(WORKER, context, values, key, check=_check_worker)


def update_worker(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    return master.update(WORKER, context, row_id, values, key, check=_check_worker)


def delete_worker(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(WORKER, context, row_id, key)


# ── 라벨 양식 ────────────────────────────────────────────────────────────────


def label_templates(context: AuthContext, **kwargs):
    return master.listing(LABEL_TEMPLATE, context, **kwargs)


def _check_label(connection, scoped, merged, _current, row_id):
    """팔레트는 QR, 나머지는 Code128(DSN-12 Q3). 종류마다 기본 양식은 하나다."""
    if (merged["label_kind"] == "PALLET") != (merged["barcode_type"] == "QR"):
        raise _invalid("barcode_type", "팔레트는 QR, 나머지는 Code128을 씁니다.")
    if not merged.get("is_default") or not merged.get("is_active"):
        return
    other = connection.execute(
        text(
            "SELECT code FROM mes.label_template WHERE workspace_id=:w AND generation_id=:g "
            "AND label_kind=:kind AND is_default AND is_active AND id IS DISTINCT FROM :id"
        ),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "kind": merged["label_kind"],
            "id": row_id,
        },
    ).scalar()
    if other is not None:
        raise _invalid("is_default", f"그 종류의 기본 양식은 이미 {other}입니다.")


def create_label_template(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(LABEL_TEMPLATE, context, values, key, check=_check_label)


def update_label_template(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(
        LABEL_TEMPLATE, context, row_id, values, key, check=_check_label
    )


def delete_label_template(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(LABEL_TEMPLATE, context, row_id, key)


# ── 공정 검사 항목 ───────────────────────────────────────────────────────────


def inspection_items(context: AuthContext, **kwargs):
    return master.listing(INSPECTION_ITEM, context, **kwargs)


def _check_inspection(connection, scoped, merged, _current, _row_id):
    if not _exists(connection, scoped, "mes.process", merged.get("process_id")):
        raise _invalid("process_id", "현재 공간의 공정을 선택하세요.")
    if not _exists(connection, scoped, "mes.item", merged.get("item_id")):
        raise _invalid("item_id", "현재 공간의 품목을 선택하세요.")
    if merged["method"] == "RANGE":
        if merged.get("lower_limit") is None and merged.get("upper_limit") is None:
            raise _invalid(
                "lower_limit", "수치 검사는 하한이나 상한 중 하나는 적습니다."
            )
        if not merged.get("unit"):
            raise _invalid("unit", "수치 검사는 단위를 적습니다.")
        low, high = merged.get("lower_limit"), merged.get("upper_limit")
        if low is not None and high is not None and float(low) > float(high):
            raise _invalid("upper_limit", "상한은 하한보다 커야 합니다.")
    elif any(
        merged.get(name) is not None for name in ("lower_limit", "upper_limit", "unit")
    ):
        raise _invalid("method", "합·부 검사는 하한·상한·단위를 쓰지 않습니다.")


def create_inspection_item(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(INSPECTION_ITEM, context, values, key, check=_check_inspection)


def update_inspection_item(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(
        INSPECTION_ITEM, context, row_id, values, key, check=_check_inspection
    )


def delete_inspection_item(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(INSPECTION_ITEM, context, row_id, key)
