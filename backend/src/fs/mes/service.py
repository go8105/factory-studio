"""MES 업무 규칙. 기준정보(M-10~M-13)는 등록·수정·삭제 흐름이 같아 공통 함수로 처리하고
화면마다 다른 검사만 check 함수로 넘긴다."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from zoneinfo import available_timezones

from sqlalchemy import Connection

from fs.common.auth import AuthContext
from fs.common.db import get_engine
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


def _read():
    engine = get_engine().execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    return engine.begin()


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
