"""ERP 기준정보 SQL. 리소스/컬럼은 서버 whitelist, 모든 업무 질의는 S로 한정한다."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text

TABLES = {
    "partners": (
        "partner",
        (
            "partner_code,partner_name,partner_kind,payment_term_days,is_active,"
            "business_no,representative,business_type,business_item,address,phone,"
            "contact_name,partner_group,credit_limit,credit_days,"
            "sale_price_group_id,purchase_price_group_id"
        ),
    ),
    "items": (
        "item",
        (
            "item_code,name,base_unit,item_type,tax_category,is_active,"
            "spec,standard_cost,standard_price,track_stock"
        ),
    ),
    "conversions": ("item_unit_conversion", "item_id,from_unit,to_unit,factor"),
    "partner-prices": (
        "partner_item_price",
        "partner_id,item_id,price_kind,unit_price,currency,effective_from,effective_to,is_active",
    ),
    "price-groups": ("price_group", "code,name,price_kind,is_active"),
    "group-prices": (
        "price_group_price",
        "price_group_id,item_id,unit_price,currency,valid_from",
    ),
    "departments": ("department", "code,name,cost_center_kind,is_active"),
    "employees": (
        "employee",
        "code,name,department_id,hr_employee_code,is_active",
    ),
    "projects": ("project", "code,name,start_on,end_on,is_active"),
    "accounts": (
        "account",
        (
            "account_code,account_name,account_class,normal_side,statement_group,"
            "requires_partner,requires_department,is_active"
        ),
    ),
    "posting-rules": (
        "posting_rule",
        "transaction_kind,line_no,entry_side,account_id,account_code,amount_basis",
    ),
    "opening-balances": (
        "opening_balance",
        "fiscal_year,account_id,partner_id,side,amount,currency",
    ),
}
# 코드 유일성을 서비스가 먼저 본다(DB UK보다 친절한 메시지).
UNIQUE = {
    "partners": ["partner_code"],
    "items": ["item_code"],
    "conversions": ["item_id", "from_unit"],
    "price-groups": ["code"],
    "group-prices": ["price_group_id", "item_id", "valid_from"],
    "departments": ["code"],
    "employees": ["code"],
    "projects": ["code"],
    "accounts": ["account_code"],
    # 거래처가 없는 기초 잔액이 있어서 NULL까지 같은 값으로 본다(IS NOT DISTINCT FROM).
    "opening-balances": ["fiscal_year", "partner_id", "account_id"],
}
REFERENCES = {
    "partners": [
        ("sales_order", "partner_id", "수주"),
        ("sales_record", "partner_id", "매출"),
        ("quotation", "partner_id", "견적"),
        ("partner_item_price", "partner_id", "거래처별 단가"),
        ("purchase_invoice", "partner_id", "매입 전표"),
        ("receipt", "partner_id", "수금"),
        ("payment", "partner_id", "지급"),
    ],
    "items": [
        ("item_unit_conversion", "item_id", "단위환산"),
        ("sales_plan_line", "item_id", "판매계획 명세"),
        ("sales_order_line", "item_id", "수주 명세"),
        ("quotation_line", "item_id", "견적 명세"),
        ("partner_item_price", "item_id", "거래처별 단가"),
        ("shipment_line", "item_id", "출하 명세"),
        ("purchase_invoice_line", "item_id", "매입 명세"),
        ("price_group_price", "item_id", "단가 그룹 단가"),
        ("sales_return_line", "item_id", "판매 반품 명세"),
        ("purchase_request_line", "item_id", "구매 요청 명세"),
        ("purchase_order_line", "item_id", "발주 명세"),
        ("purchase_return_line", "item_id", "구매 반품 명세"),
        ("cost_item_result", "item_id", "재고자산 평가"),
        ("cost_allocation", "item_id", "제조원가 배부"),
    ],
    "price-groups": [
        ("price_group_price", "price_group_id", "단가 그룹 단가"),
        ("partner", "sale_price_group_id", "거래처 판매 단가 그룹"),
        ("partner", "purchase_price_group_id", "거래처 구매 단가 그룹"),
    ],
    "departments": [
        ("employee", "department_id", "담당자"),
        ("purchase_request", "department_id", "구매 요청"),
        ("purchase_order", "department_id", "발주서"),
        ("purchase_invoice", "department_id", "매입 전표"),
        ("journal_entry", "department_id", "전표"),
        ("journal_line", "department_id", "전표 라인"),
        ("expense_claim", "department_id", "지출결의서"),
        ("card_transaction", "department_id", "카드 사용 내역"),
        ("budget_line", "department_id", "예산 명세"),
        ("fixed_asset", "department_id", "고정자산"),
    ],
    "employees": [
        ("purchase_request", "employee_id", "구매 요청"),
        ("journal_entry", "employee_id", "전표"),
        ("expense_claim", "employee_id", "지출결의서"),
        ("corporate_card", "employee_id", "법인카드"),
    ],
    "projects": [
        ("purchase_order", "project_id", "발주서"),
        ("purchase_invoice", "project_id", "매입 전표"),
        ("journal_line", "project_id", "전표 라인"),
        ("expense_claim_line", "project_id", "지출결의 명세"),
        ("card_transaction", "project_id", "카드 사용 내역"),
    ],
    # 계정은 삭제하지 않는다(사용중단만). 분류·정상 잔액을 바꿀 수 있는지 볼 때 쓴다.
    "accounts": [
        ("posting_rule", "account_id", "분개규칙"),
        ("journal_line", "account_id", "전표 라인"),
        ("expense_claim_line", "account_id", "지출결의 명세"),
        ("opening_balance", "account_id", "기초 잔액"),
        ("bank_account", "account_id", "계좌"),
        ("corporate_card", "account_id", "법인카드"),
        ("budget_line", "account_id", "예산 명세"),
    ],
}


def scope(context):
    return {"w": context.workspace_id, "g": context.generation_id}


def camel(key):
    first, *rest = key.split("_")
    return first + "".join(x.title() for x in rest)


def present(row):
    return {
        camel(k): str(v)
        if isinstance(v, Decimal)
        else v.isoformat()
        if isinstance(v, (date, datetime))
        else v
        for k, v in row.items()
    }


def columns(resource):
    return "id," + TABLES[resource][1] + ",created_at"


def get(connection, context, resource, row_id, parent=None):
    where = "workspace_id=:w AND generation_id=:g AND id=:id"
    if parent is not None:
        where += " AND item_id=:parent"
    row = (
        connection.execute(
            text(
                f"SELECT {columns(resource)} FROM erp.{TABLES[resource][0]} WHERE {where}"
            ),
            {**scope(context), "id": row_id, "parent": parent},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def listing(connection, context, resource, order, offset, limit, filters):
    where = "workspace_id=:w AND generation_id=:g"
    params = {**scope(context), "offset": offset, "limit": limit}
    for key, value in filters.items():
        if value is not None:
            where += f" AND {key}=:{key}"
            params[key] = value
    table = TABLES[resource][0]
    total = connection.execute(
        text(f"SELECT count(*) FROM erp.{table} WHERE {where}"), params
    ).scalar_one()
    rows = connection.execute(
        text(
            f"SELECT {columns(resource)} FROM erp.{table} WHERE {where} ORDER BY {order},id OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [present(row) for row in rows], total


def duplicate(connection, context, resource, values, row_id):
    fields = UNIQUE.get(resource)
    if not fields:
        return False
    where = " AND ".join(f"{field} IS NOT DISTINCT FROM :{field}" for field in fields)
    return (
        connection.execute(
            text(
                f"SELECT 1 FROM erp.{TABLES[resource][0]} WHERE workspace_id=:w AND generation_id=:g AND {where} AND id IS DISTINCT FROM :id"
            ),
            {**scope(context), **values, "id": row_id},
        ).first()
        is not None
    )


def references(connection, context, resource, row_id):
    result = []
    for table, column, label in REFERENCES.get(resource, []):
        count = connection.execute(
            text(
                f"SELECT count(*) FROM erp.{table} WHERE workspace_id=:w AND generation_id=:g AND {column}=:id"
            ),
            {**scope(context), "id": row_id},
        ).scalar_one()
        if count:
            result.append({"table": f"erp.{table}", "label": label, "count": count})
    return result


def overlaps(connection, context, values, row_id):
    return (
        connection.execute(
            text("""SELECT id,effective_from,effective_to FROM erp.partner_item_price
        WHERE workspace_id=:w AND generation_id=:g AND partner_id=:partner_id AND item_id=:item_id
        AND id IS DISTINCT FROM :id
        AND effective_from <= COALESCE(:effective_to,'9999-12')
        AND (effective_to IS NULL OR effective_to >= :effective_from) ORDER BY effective_from,id"""),
            {**scope(context), **values, "id": row_id},
        )
        .mappings()
        .all()
    )


def store(connection, context, resource, values, row_id):
    table = TABLES[resource][0]
    allowed = set(TABLES[resource][1].split(","))
    assert set(values) <= allowed
    if row_id is None:
        names = ",".join(values)
        binds = ",".join(":" + name for name in values)
        sql = f"INSERT INTO erp.{table} (workspace_id,generation_id,{names}) VALUES (:w,:g,{binds})"
    else:
        assignments = ",".join(f"{name}=:{name}" for name in values)
        sql = f"UPDATE erp.{table} SET {assignments} WHERE workspace_id=:w AND generation_id=:g AND id=:id"
    row = (
        connection.execute(
            text(sql + f" RETURNING {columns(resource)}"),
            {**scope(context), **values, "id": row_id},
        )
        .mappings()
        .one()
    )
    return present(row)


def delete(connection, context, resource, row_id):
    connection.execute(
        text(
            f"DELETE FROM erp.{TABLES[resource][0]} WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**scope(context), "id": row_id},
    )
