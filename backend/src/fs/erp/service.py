"""ERP 쓰기: 공간 잠금/세대 재확인 → 멱등 확인 → 검증 → 저장/영수증."""

from decimal import Decimal

from fs.common.db import get_engine
from fs.common.engine import read
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import read_scope, write_scope
from fs.erp import repository as repo


def invalid(field, message):
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {repo.camel(field): message}},
    )


def not_found():
    return ApiError(404, "NOT_FOUND", "대상을 찾을 수 없습니다.")


# 공통 엔진: 조회 트랜잭션(REPEATABLE READ · 읽기 전용)
_read = read


def listing(context, resource, offset, limit, sort, filters):
    allowed = {
        repo.camel(key): key
        for key in ("id," + repo.TABLES[resource][1] + ",created_at").split(",")
    }
    if sort:
        field, _, direction = sort.partition(":")
        if field not in allowed or direction not in ("asc", "desc"):
            raise invalid("sort", "지원하지 않는 정렬입니다.")
        order = f"{allowed[field]} {direction.upper()}"
    else:
        order = repo.TABLES[resource][1].split(",")[0] + " ASC"
    with _read() as connection:
        scoped = read_scope(connection, context, "erp")
        if (
            resource == "conversions"
            and repo.get(connection, scoped, "items", filters["item_id"]) is None
        ):
            raise not_found()
        return repo.listing(connection, scoped, resource, order, offset, limit, filters)


def detail(context, resource, row_id, parent=None):
    with _read() as connection:
        scoped = read_scope(connection, context, "erp")
        row = repo.get(connection, scoped, resource, row_id, parent)
        if row is None:
            raise not_found()
        return repo.present(row)


# 같은 공간의 대상을 가리키는지 본다. 다른 공간의 id를 넣으면 DB FK가 아니라 여기서 막힌다.
LINKS = {
    "employees": [("department_id", "departments")],
    "group-prices": [("price_group_id", "price-groups"), ("item_id", "items")],
    "partners": [
        ("sale_price_group_id", "price-groups"),
        ("purchase_price_group_id", "price-groups"),
    ],
}
# 단가 그룹은 쓰임새가 정해져 있다. 판매 그룹을 매입 자리에 넣으면 단가가 조용히 어긋난다.
GROUP_KIND = {"sale_price_group_id": "SALE", "purchase_price_group_id": "PURCHASE"}


def _related(connection, scoped, resource, merged):
    for field, target in LINKS.get(resource, []):
        value = merged.get(field)
        if value is None:
            continue
        row = repo.get(connection, scoped, target, value)
        if row is None:
            raise invalid(field, "현재 공간의 대상을 선택하세요.")
        wanted = GROUP_KIND.get(field)
        if wanted and row["price_kind"] != wanted:
            raise invalid(
                field,
                "판매 단가 그룹을 선택하세요."
                if wanted == "SALE"
                else "구매 단가 그룹을 선택하세요.",
            )


def validate(connection, scoped, resource, values, current, row_id):
    merged = {**(current or {}), **values}
    if repo.duplicate(connection, scoped, resource, merged, row_id):
        raise invalid(repo.UNIQUE[resource][-1], "이미 사용 중인 값입니다.")
    _related(connection, scoped, resource, merged)
    if resource == "items" and current and merged["base_unit"] != current["base_unit"]:
        refs = repo.references(connection, scoped, resource, row_id)
        if refs:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "참조 중인 품목의 기준 단위는 바꿀 수 없습니다.",
                {"reason": "UNIT_IN_USE", "references": refs},
            )
    if resource == "conversions":
        item = repo.get(connection, scoped, "items", merged["item_id"])
        if item is None:
            raise not_found()
        values["to_unit"] = item["base_unit"]
        if merged["from_unit"] == item["base_unit"]:
            raise invalid("from_unit", "기준 단위와 다른 단위를 입력하세요.")
        if Decimal(merged["factor"]) <= 0:
            raise invalid("factor", "환산 계수는 0보다 커야 합니다.")
    if resource == "projects":
        start, end = merged["start_on"], merged["end_on"]
        if start and end and end < start:
            raise invalid("end_on", "종료일은 시작일 이후여야 합니다.")
    if resource == "accounts" and current:
        changed = [
            f for f in ("account_class", "normal_side") if merged[f] != current[f]
        ]
        if changed:
            refs = repo.references(connection, scoped, resource, row_id)
            if refs:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "쓰이고 있는 계정의 분류와 정상 잔액은 바꿀 수 없습니다.",
                    {"reason": "ACCOUNT_IN_USE", "references": refs},
                )
    if resource == "partner-prices":
        for field, target in [("partner_id", "partners"), ("item_id", "items")]:
            if repo.get(connection, scoped, target, merged[field]) is None:
                raise invalid(field, "현재 공간의 대상을 선택하세요.")
        if (
            merged["effective_to"] is not None
            and merged["effective_to"] < merged["effective_from"]
        ):
            raise invalid("effective_to", "종료월은 시작월 이후여야 합니다.")
        conflicts = repo.overlaps(connection, scoped, merged, row_id)
        if conflicts:
            raise ApiError(
                409,
                "PERIOD_OVERLAP",
                "같은 거래처·품목의 적용 구간이 겹칩니다.",
                {
                    "reason": "PERIOD_OVERLAP",
                    "references": [{"label": "겹치는 단가", "count": len(conflicts)}],
                    "conflicts": [repo.present(r) for r in conflicts],
                },
            )


def mutate(context, resource, values, key, row_id=None, parent=None, deleting=False):
    if resource == "posting-rules":
        raise ApiError(405, "HTTP_ERROR", "읽기 전용입니다.")
    # 계정은 더하고 사용중단할 뿐 지우지 않는다(DSN-11 F41). 지난 전표가 계정을 잃는다.
    if resource == "accounts" and deleting:
        raise ApiError(405, "HTTP_ERROR", "계정은 삭제 대신 사용 여부를 끕니다.")
    if not deleting:
        if row_id is not None and not values:
            raise invalid("body", "변경할 항목이 없습니다.")
        nullable = {
            "partners": {"payment_term_days"}
            | set(repo.TABLES["partners"][1].split(",")[5:]),
            "partner-prices": {"effective_to"},
            "items": {"spec", "standard_cost", "standard_price"},
            "employees": {"hr_employee_code"},
            "projects": {"start_on", "end_on"},
            "accounts": {"statement_group"},
        }.get(resource, set())
        for field, value in values.items():
            if value is None and field not in nullable:
                raise invalid(field, "null로 비울 수 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, "erp")
        operation = f"erp.{resource}.{'delete' if deleting else 'create' if row_id is None else 'update'}"
        digest = request_digest({"id": row_id, "parent": parent, **values})
        cached = find_receipt(connection, scoped, operation, key, digest)
        if cached is not None:
            return cached
        current = (
            repo.get(connection, scoped, resource, row_id, parent)
            if row_id is not None
            else None
        )
        if row_id is not None and current is None:
            raise not_found()
        if parent is not None:
            if repo.get(connection, scoped, "items", parent) is None:
                raise not_found()
            values = {**values, "item_id": parent}
        if deleting:
            refs = repo.references(connection, scoped, resource, row_id)
            if refs:
                raise ApiError(
                    409,
                    "REFERENCED_BY_OTHERS",
                    "참조 중인 항목은 삭제할 수 없습니다.",
                    {"reason": "REFERENCED_BY_OTHERS", "references": refs},
                )
            repo.delete(connection, scoped, resource, row_id)
            result = {}
            status = 204
        else:
            validate(connection, scoped, resource, values, current, row_id)
            result = repo.store(connection, scoped, resource, values, row_id)
            status = 201 if row_id is None else 200
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            repo.TABLES[resource][0],
            row_id or result["id"],
            result,
            status,
        )
        return result
