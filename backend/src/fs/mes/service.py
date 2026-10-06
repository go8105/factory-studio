"""MES 업무 규칙. 기준정보(M-10~M-13)는 등록·수정·삭제 흐름이 같아 공통 함수로 처리하고
화면마다 다른 검사만 check 함수로 넘긴다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from typing import Any
from zoneinfo import available_timezones

from sqlalchemy import Connection

from fs.common.auth import AuthContext
from fs.common.db import get_engine
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import read_scope, write_scope
from fs.mes import repository as repo
from fs.mes.repository import Master

MODULE = "mes"
# check(connection, scoped, 최종 값, 현재 행 또는 None) → 함께 저장할 추가 컬럼
Check = Callable[
    [Connection, AuthContext, dict[str, Any], dict[str, Any] | None], dict[str, Any]
]


# 공통 엔진: 조회 트랜잭션(REPEATABLE READ · 읽기 전용)
_read = read


def _field(field: str, message: str) -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {field: message}},
    )


def _not_found(label: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{label}을(를) 찾을 수 없습니다.")


def _snake(name: str) -> str:
    return "".join(f"_{c.lower()}" if c.isupper() else c for c in name)


def _code_check(
    connection: Connection,
    scoped: AuthContext,
    master: Master,
    final: dict[str, Any],
    current: dict[str, Any] | None,
) -> None:
    scope = final.get(master.code_scope) if master.code_scope else None
    if repo.code_taken(
        connection,
        scoped,
        master,
        final[master.code],
        scope,
        None if current is None else current["id"],
    ):
        raise _field(repo._camel(master.code), "이미 사용 중인 코드입니다.")


def list_rows(context: AuthContext, master: Master) -> list[dict[str, Any]]:
    with _read() as connection:
        return repo.list_rows(
            connection, read_scope(connection, context, MODULE), master
        )


def get_row(
    context: AuthContext, master: Master, row_id: int, label: str
) -> dict[str, Any]:
    with _read() as connection:
        found = repo.get_row(
            connection, read_scope(connection, context, MODULE), master, row_id
        )
    if found is None:
        raise _not_found(label)
    return found


def create(
    context: AuthContext,
    master: Master,
    values: dict[str, Any],
    key: str,
    check: Check,
    after: Callable[[Connection, AuthContext, dict[str, Any]], dict[str, Any]]
    | None = None,
) -> dict[str, Any]:
    entity = master.table.split(".")[1]
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = f"mes.{entity}.create"
        digest = request_digest(values)
        cached = find_receipt(connection, scoped, operation, key, digest)
        if cached is not None:
            return cached
        own, extra = _split(values)
        own |= check(connection, scoped, own, None)
        _code_check(connection, scoped, master, own, None)
        created = repo.insert_row(connection, scoped, master, own)
        if after is not None:
            created = after(connection, scoped, {**created, **extra})
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            entity,
            created["id"],
            created,
            201,
        )
        return created


def update(
    context: AuthContext,
    master: Master,
    row_id: int,
    values: dict[str, Any],
    key: str,
    check: Check,
    label: str,
    after: Callable[[Connection, AuthContext, dict[str, Any]], dict[str, Any]]
    | None = None,
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    entity = master.table.split(".")[1]
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = f"mes.{entity}.update"
        digest = request_digest({"id": row_id, **values})
        cached = find_receipt(connection, scoped, operation, key, digest)
        if cached is not None:
            return cached
        current = repo.get_row(connection, scoped, master, row_id)
        if current is None:
            raise _not_found(label)
        own, extra = _split(values)
        final = {_snake(k): v for k, v in current.items()} | own
        own |= check(connection, scoped, final, current)
        _code_check(connection, scoped, master, final, current)
        updated = (
            repo.update_row(connection, scoped, master, row_id, own) if own else current
        )
        if after is not None:
            updated = after(connection, scoped, {**updated, **extra})
        save_receipt(
            connection, scoped, operation, key, digest, entity, row_id, updated
        )
        return updated


def delete(
    context: AuthContext,
    master: Master,
    row_id: int,
    key: str,
    label: str,
    before: Callable[[Connection, AuthContext], None] | None = None,
) -> None:
    entity = master.table.split(".")[1]
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = f"mes.{entity}.delete"
        digest = request_digest({"id": row_id})
        if find_receipt(connection, scoped, operation, key, digest) is not None:
            return
        if repo.get_row(connection, scoped, master, row_id) is None:
            raise _not_found(label)
        references = repo.count_references(
            connection, scoped, master.references, row_id
        )
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                f"다른 데이터가 참조 중인 {label}은(는) 삭제할 수 없습니다.",
                {"references": references},
            )
        if before is not None:
            before(connection, scoped)
        repo.delete_row(connection, scoped, master, row_id)
        save_receipt(
            connection, scoped, operation, key, digest, entity, row_id, {}, 204
        )


# 요청 본문 중 테이블 컬럼이 아닌 값(공정의 허용 설비 목록)은 따로 처리한다.
_EXTRA = ("equipment_ids",)


def _split(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    own = {k: v for k, v in values.items() if k not in _EXTRA}
    extra = {k: v for k, v in values.items() if k in _EXTRA}
    return own, extra


# ---- M-10 사업장·공간 ----
def check_site(connection, scoped, final, current) -> dict[str, Any]:
    if final["timezone"] not in available_timezones():
        raise _field("timezone", "IANA 시간대 이름이어야 합니다(예: Asia/Seoul).")
    return {}


def check_location(connection, scoped, final, current) -> dict[str, Any]:
    site_id = final["site_id"]
    if current is None and repo.get_row(connection, scoped, repo.SITE, site_id) is None:
        raise _field("siteId", "유효하지 않은 사업장입니다.")
    parent_id = final.get("parent_location_id")
    if parent_id is not None:
        parent = repo.get_row(connection, scoped, repo.LOCATION, parent_id)
        if parent is None or parent["siteId"] != site_id:
            raise _field(
                "parentLocationId", "같은 사업장의 공간만 상위로 지정할 수 있습니다."
            )
        if current is not None and current["id"] in repo.location_ancestors(
            connection, scoped, parent_id
        ):
            raise _field(
                "parentLocationId",
                "자기 자신이나 하위 공간을 상위로 지정할 수 없습니다.",
            )
    return {}


# ---- M-11 설비 ----
def check_equipment(connection, scoped, final, current) -> dict[str, Any]:
    if repo.get_row(connection, scoped, repo.LOCATION, final["location_id"]) is None:
        raise _field("locationId", "유효하지 않은 공간입니다.")
    return {}


# ---- M-12 품목·단위 환산 ----
def check_item(connection, scoped, final, current) -> dict[str, Any]:
    # 단위 환산·작업지시가 (품목, 기준 단위)를 함께 참조한다. 바꾸면 기존 수량의 단위가 거짓이 된다.
    if current is not None and final["base_unit"] != current["baseUnit"]:
        references = repo.count_references(
            connection, scoped, repo.ITEM_UNIT_REFERENCES, current["id"]
        )
        if references:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "단위 환산이나 작업지시가 있는 품목은 기준 단위를 바꿀 수 없습니다.",
                {"reason": "UNIT_IN_USE", "references": references},
            )
    return {}


def items_with_conversions(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        items = repo.list_rows(connection, scoped, repo.ITEM)
        conversions = repo.list_rows(connection, scoped, repo.CONVERSION)
    by_item: dict[int, list[dict[str, Any]]] = {}
    for c in conversions:
        by_item.setdefault(c["itemId"], []).append(c)
    return [{**i, "conversions": by_item.get(i["id"], [])} for i in items]


def conversion_check(item_id: int) -> Check:
    def check(connection, scoped, final, current) -> dict[str, Any]:
        item = repo.get_row(connection, scoped, repo.ITEM, item_id)
        if item is None:
            raise _not_found("품목")
        if current is not None and current["itemId"] != item_id:
            raise _not_found("단위 환산")
        if Decimal(final["factor"]) <= 0:
            raise _field("factor", "환산 계수는 0보다 커야 합니다.")
        # 환산 결과 단위는 품목의 기준 단위로 고정한다(복합 FK).
        if final["from_unit"] == item["baseUnit"]:
            raise _field("fromUnit", "기준 단위와 다른 단위여야 합니다.")
        return {"item_id": item_id, "to_unit": item["baseUnit"]}

    return check


def conversion_owner(item_id: int, row_id: int):
    """삭제 경로의 품목과 환산 행의 품목이 같은지 확인한다."""

    def before(connection, scoped) -> None:
        row = repo.get_row(connection, scoped, repo.CONVERSION, row_id)
        if row is None or row["itemId"] != item_id:
            raise _not_found("단위 환산")

    return before


# ---- M-13 공정 ----
def processes_with_equipment(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        processes = repo.list_rows(connection, scoped, repo.PROCESS)
        links = repo.process_equipment_ids(connection, scoped)
    return [{**p, "equipmentIds": links.get(p["id"], [])} for p in processes]


def check_process(connection, scoped, final, current) -> dict[str, Any]:
    return {}


def save_process_equipment(connection, scoped, row: dict[str, Any]) -> dict[str, Any]:
    """허용 설비 목록을 통째로 바꾼다. 요청에 목록이 없으면 그대로 둔다."""
    ids = row.pop("equipment_ids", None)
    if ids is not None:
        ids = sorted(set(ids))
        missing = set(ids) - repo.existing_ids(connection, scoped, "mes.equipment", ids)
        if missing:
            raise _field("equipmentIds", "유효하지 않은 설비가 있습니다.")
        repo.replace_process_equipment(connection, scoped, row["id"], ids)
    links = repo.process_equipment_ids(connection, scoped)
    return {**row, "equipmentIds": links.get(row["id"], [])}


def delete_process_links(process_id: int):
    def before(connection, scoped) -> None:
        repo.replace_process_equipment(connection, scoped, process_id, [])

    return before


# ---- M-14 공정 경로 · M-15 BOM ----
# 두 화면은 같은 버전 규칙을 따른다: 초안(draft)만 편집, 게시(published)·폐기(retired)는 불변,
# 바꾸려면 새 버전으로 개정한다(schema.json SERVICE: route_version·bom_version).
@dataclass(frozen=True)
class Versioned:
    master: Master
    child: Master
    parent_column: str
    number: str  # 버전 번호 컬럼
    number_key: str  # 버전 번호를 매기는 범위 컬럼(경로 코드 / 품목)
    label: str
    children_label: str


ROUTES = Versioned(
    repo.ROUTE,
    repo.STEP,
    "route_version_id",
    "version",
    "route_code",
    "공정 경로",
    "공정 단계",
)
BOMS = Versioned(
    repo.BOM, repo.LINE, "bom_version_id", "version_no", "item_id", "BOM", "구성 자재"
)


def _locked(message: str, reason: str) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason})


# 공통 엔진(fs.common.engine.action): 공간 잠금 → 멱등 영수증 → 처리 → 영수증 저장
_action = partial(action, MODULE)


def _with_children(
    connection, scoped, v: Versioned, row: dict[str, Any]
) -> dict[str, Any]:
    children = repo.list_rows(connection, scoped, v.child, {v.parent_column: row["id"]})
    key = "steps" if v is ROUTES else "lines"
    return {**row, key: children}


def list_versions(context: AuthContext, v: Versioned) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = repo.list_rows(connection, scoped, v.master)
        children = repo.list_rows(connection, scoped, v.child)
    key = "steps" if v is ROUTES else "lines"
    by_parent: dict[int, list[dict[str, Any]]] = {}
    for c in children:
        by_parent.setdefault(c[repo._camel(v.parent_column)], []).append(c)
    return [{**r, key: by_parent.get(r["id"], [])} for r in rows]


def _get_version(connection, scoped, v: Versioned, row_id: int) -> dict[str, Any]:
    row = repo.get_row(connection, scoped, v.master, row_id)
    if row is None:
        raise _not_found(v.label)
    return row


def _no_draft(connection, scoped, v: Versioned, key_value: Any) -> None:
    if repo.exists_where(
        connection, scoped, v.master.table, {v.number_key: key_value, "status": "draft"}
    ):
        raise _locked(
            f"이미 편집 중인 {v.label} 초안이 있습니다. 그 초안을 이어서 편집하세요.",
            "DRAFT_EXISTS",
        )


def create_version(
    context: AuthContext, v: Versioned, values: dict[str, Any], key: str
):
    def run(connection, scoped):
        if repo.get_row(connection, scoped, repo.ITEM, values["item_id"]) is None:
            raise _field("itemId", "유효하지 않은 품목입니다.")
        code = v.master.code
        if repo.exists_where(connection, scoped, v.master.table, {code: values[code]}):
            hint = " 기존 버전을 개정하세요." if v is ROUTES else ""
            raise _field(repo._camel(code), f"이미 있는 코드입니다.{hint}")
        _no_draft(connection, scoped, v, values[v.number_key])
        number = repo.next_number(
            connection,
            scoped,
            v.master.table,
            v.number,
            v.number_key,
            values[v.number_key],
        )
        row = repo.insert_row(
            connection, scoped, v.master, {**values, v.number: number}
        )
        return _with_children(connection, scoped, v, row), v.master.table, row["id"]

    return _action(context, f"{v.master.table}.create", key, values, run, 201)


def revise_version(
    context: AuthContext, v: Versioned, row_id: int, values: dict[str, Any], key: str
):
    """게시·폐기 버전을 복사해 다음 번호의 초안을 만든다."""

    def run(connection, scoped):
        source = _get_version(connection, scoped, v, row_id)
        if source["status"] == "draft":
            raise _locked("초안은 개정하지 않고 바로 편집합니다.", "IS_DRAFT")
        key_value = source[repo._camel(v.number_key)]
        _no_draft(connection, scoped, v, key_value)
        code = v.master.code
        new_code = values.get(code, source[repo._camel(code)])
        if v is BOMS and repo.exists_where(
            connection, scoped, v.master.table, {code: new_code}
        ):
            raise _field(
                repo._camel(code), "이미 있는 코드입니다. 새 BOM 코드를 입력하세요."
            )
        number = repo.next_number(
            connection, scoped, v.master.table, v.number, v.number_key, key_value
        )
        row = repo.insert_row(
            connection,
            scoped,
            v.master,
            {"item_id": source["itemId"], code: new_code, v.number: number},
        )
        children = repo.list_rows(
            connection, scoped, v.child, {v.parent_column: row_id}
        )
        skip = {"id", "createdAt", repo._camel(v.parent_column)}
        repo.replace_children(
            connection,
            scoped,
            v.child.table,
            v.parent_column,
            row["id"],
            [{_snake(k): c[k] for k in c if k not in skip} for c in children],
        )
        return _with_children(connection, scoped, v, row), v.master.table, row["id"]

    return _action(
        context, f"{v.master.table}.revise", key, {"id": row_id, **values}, run, 201
    )


def set_children(
    context: AuthContext,
    v: Versioned,
    row_id: int,
    rows: list[dict[str, Any]],
    key: str,
    validate: Callable[
        [Connection, AuthContext, dict[str, Any], list[dict[str, Any]]],
        list[dict[str, Any]],
    ],
):
    """초안의 공정 단계 / 구성 자재를 요청 순서대로 통째로 바꾼다."""

    def run(connection, scoped):
        version = _get_version(connection, scoped, v, row_id)
        if version["status"] != "draft":
            raise _locked(
                f"게시·폐기된 {v.label}은(는) 바꿀 수 없습니다. 개정해서 새 버전으로 편집하세요.",
                "VERSION_LOCKED",
            )
        children = validate(connection, scoped, version, rows)
        repo.replace_children(
            connection, scoped, v.child.table, v.parent_column, row_id, children
        )
        return _with_children(connection, scoped, v, version), v.master.table, row_id

    return _action(
        context, f"{v.master.table}.children", key, {"id": row_id, "rows": rows}, run
    )


def transition(context: AuthContext, v: Versioned, row_id: int, target: str, key: str):
    def run(connection, scoped):
        version = _get_version(connection, scoped, v, row_id)
        source = {"published": "draft", "retired": "published"}[target]
        if version["status"] != source:
            done = "게시" if target == "published" else "폐기"
            raise _locked(
                f"{version['status']} 상태에서는 {done}할 수 없습니다.",
                "INVALID_TRANSITION",
            )
        if target == "published" and not repo.exists_where(
            connection, scoped, v.child.table, {v.parent_column: row_id}
        ):
            raise _locked(
                f"{v.children_label}이(가) 없는 {v.label}은(는) 게시할 수 없습니다.",
                "EMPTY_VERSION",
            )
        # 폐기 시각은 경로에만 있다(bom_version에는 retired_at 컬럼이 없다).
        stamp = (
            "published_at"
            if target == "published"
            else ("retired_at" if v is ROUTES else None)
        )
        row = repo.set_status(connection, scoped, v.master, row_id, target, stamp)
        return _with_children(connection, scoped, v, row), v.master.table, row_id

    return _action(context, f"{v.master.table}.{target}", key, {"id": row_id}, run)


def delete_version(context: AuthContext, v: Versioned, row_id: int, key: str) -> None:
    def run(connection, scoped):
        version = _get_version(connection, scoped, v, row_id)
        if version["status"] != "draft":
            raise _locked(
                "초안만 삭제할 수 있습니다. 게시한 버전은 폐기하세요.", "VERSION_LOCKED"
            )
        references = repo.count_references(
            connection, scoped, v.master.references, row_id
        )
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                f"다른 데이터가 참조 중인 {v.label}은(는) 삭제할 수 없습니다.",
                {"references": references},
            )
        repo.replace_children(
            connection, scoped, v.child.table, v.parent_column, row_id, []
        )
        repo.delete_row(connection, scoped, v.master, row_id)
        return {}, v.master.table, row_id

    _action(context, f"{v.master.table}.delete", key, {"id": row_id}, run, 204)


def validate_steps(connection, scoped, version, rows) -> list[dict[str, Any]]:
    ids = [r["process_id"] for r in rows]
    if set(ids) - repo.existing_ids(connection, scoped, "mes.process", ids):
        raise _field("steps", "유효하지 않은 공정이 있습니다.")
    # 같은 공정을 두 번 거치는 경로(재검사 등)는 허용한다. 순서는 요청 순서 1, 2, 3 …
    return [{"process_id": pid, "sequence_no": n} for n, pid in enumerate(ids, 1)]


def validate_lines(connection, scoped, version, rows) -> list[dict[str, Any]]:
    items = {i["id"]: i for i in repo.list_rows(connection, scoped, repo.ITEM)}
    conversions = repo.list_rows(connection, scoped, repo.CONVERSION)
    seen: set[int] = set()
    result = []
    for n, r in enumerate(rows, 1):
        material = items.get(r["material_item_id"])
        where = f"{n}번째 자재: "
        if material is None:
            raise _field("lines", where + "유효하지 않은 품목입니다.")
        if material["id"] == version["itemId"]:
            raise _field("lines", where + "만들 품목 자신은 자재가 될 수 없습니다.")
        if material["id"] in seen:
            raise _field("lines", where + "같은 자재가 이미 있습니다.")
        seen.add(material["id"])
        units = {material["baseUnit"]} | {
            c["fromUnit"] for c in conversions if c["itemId"] == material["id"]
        }
        if r["unit"] not in units:
            raise _field(
                "lines",
                where + f"단위는 {', '.join(sorted(units))} 중 하나여야 합니다.",
            )
        if Decimal(r["qty_per_unit"]) <= 0:
            raise _field("lines", where + "소요량은 0보다 커야 합니다.")
        if not 0 <= Decimal(r["loss_rate"]) < 100:
            raise _field("lines", where + "손실률은 0 이상 100 미만입니다.")
        result.append({**r, "line_no": n})
    return result
