"""TX-09 매출 인식 (FS-006a·FS-014b). 독립 트랜잭션이 아니라 출하 확정(TX-08) 안에서 부른다.

세액 정책은 이 파일 한 곳에서만 계산한다(호출부에서 재계산 금지):
- 품목 과세구분 TAXABLE 10%, ZERO·EXEMPT 0% (E-G01: 세율은 코드 상수).
- 명세별 공급가액(수량 × 수주 단가)과 세액(공급가액 × 세율)을 각각 1원 단위 사사오입한 뒤 합산.
- 채권은 같은 트랜잭션에서 원금 = 합계로 1건. 만기 = 인식일(Asia/Seoul) + 거래처 결제일수, 조건 없으면 NULL.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text

TAX_RATE = {"TAXABLE": Decimal("0.10"), "ZERO": Decimal(0), "EXEMPT": Decimal(0)}
WON = Decimal(1)

LINES_SQL = """
SELECT sl.shipped_qty, l.unit_price, i.tax_category
FROM erp.shipment_line sl
JOIN erp.shipment_order_line sol ON sol.workspace_id=sl.workspace_id
 AND sol.generation_id=sl.generation_id AND sol.id=sl.shipment_order_line_id
JOIN erp.sales_order_line l ON l.workspace_id=sol.workspace_id
 AND l.generation_id=sol.generation_id AND l.id=sol.sales_order_line_id
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE sl.workspace_id=:w AND sl.generation_id=:g AND sl.shipment_id=:id
ORDER BY sl.id"""


def amounts(lines) -> tuple[Decimal, Decimal]:
    """(공급가액, 세액). lines: (수량, 단가, 과세구분)."""
    supply = tax = Decimal(0)
    for qty, price, category in lines:
        line_supply = (Decimal(qty) * Decimal(price)).quantize(WON, ROUND_HALF_UP)
        supply += line_supply
        tax += (line_supply * TAX_RATE[category]).quantize(WON, ROUND_HALF_UP)
    return supply, tax


def recognize(connection, scoped, shipment_id: int, partner_id: int) -> int:
    params = {"w": scoped.workspace_id, "g": scoped.generation_id, "id": shipment_id}
    rows = connection.execute(text(LINES_SQL), params).all()
    supply, tax = amounts(rows)
    record_id = connection.execute(
        text(
            "INSERT INTO erp.sales_record (workspace_id, generation_id, shipment_id, "
            "partner_id, supply_amount, tax_amount, total_amount, recognized_at) "
            "SELECT :w, :g, :id, :p, :s, :t, :total, shipped_at FROM erp.shipment "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING id"
        ),
        {**params, "p": partner_id, "s": supply, "t": tax, "total": supply + tax},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO erp.receivable (workspace_id, generation_id, sales_record_id, "
            "partner_id, amount, due_date) "
            "SELECT r.workspace_id, r.generation_id, r.id, r.partner_id, r.total_amount, "
            "(r.recognized_at AT TIME ZONE 'Asia/Seoul')::date + p.payment_term_days "
            "FROM erp.sales_record r JOIN erp.partner p ON p.workspace_id=r.workspace_id "
            "AND p.generation_id=r.generation_id AND p.id=r.partner_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.id=:r"
        ),
        {**params, "r": record_id},
    )
    return record_id


if __name__ == "__main__":
    # 1원 사사오입은 명세마다: 3 × 333.35 = 1000.05 → 1000, 세액 100 / ZERO는 세액 0
    assert amounts([("3", "333.35", "TAXABLE"), ("1", "5", "ZERO")]) == (1005, 100)
    assert amounts([("1", "4.5", "TAXABLE")]) == (5, 1)  # 4.5→5, 0.5→1
    print("ok")
