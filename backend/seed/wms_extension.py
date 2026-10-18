"""FS-026 deterministic WMS-only examples for new templates; no production backfill."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from seed.common import at


def append_examples(writer, houses, locations, items):
    day = writer.seed_date
    stamp = at(day, -1, 11)
    extra = writer.add(
        "wms.storage_location",
        [
            {
                "warehouse_id": houses[h],
                "code": code,
                "name": name,
                "is_default": False,
                "is_active": True,
                "location_type": ltype,
            }
            for h, code, name, ltype in [
                ("WH-RAW", "R-Q01", "원자재 격리", "QUARANTINE"),
                ("WH-FG", "F-Q01", "완제품 격리", "QUARANTINE"),
                ("WH-RAW", "R-REC", "원자재 입고장", "RECEIVING"),
                ("WH-FG", "F-REC", "완제품 입고장", "RECEIVING"),
            ]
        ],
        "code",
    )
    locations = {**locations, **extra}
    inspected_no = f"IN-{day:%Y%m%d}-003"
    doc_no = f"WD-{day - timedelta(days=1):%Y%m%d}-901"
    doc = writer.add(
        "wms.stock_document",
        [
            {
                "document_no": doc_no,
                "document_type": "WMS_INSPECTION",
                "status": "posted",
                "source_key": "WMS:INSPECTION:" + inspected_no,
                "source_ref": inspected_no,
                "document_on": day - timedelta(days=1),
                "document_month": f"{day - timedelta(days=1):%Y-%m}",
                "posted_at": stamp,
                "created_at": stamp,
                "note": "합성 검수 예시: 합격95/격리3/부족2 KG",
            }
        ],
        "document_no",
    )[doc_no]
    writer.add(
        "wms.stock_move",
        [
            {
                "document_id": doc,
                "line_no": n,
                "item_id": items["RM-PBT"],
                "location_id": locations[loc],
                "qty_delta": Decimal(qty),
                "source_qty": Decimal(qty),
                "source_unit": "KG",
                "moved_at": stamp,
                "created_at": stamp,
            }
            for n, (loc, qty) in enumerate([("R-A01", "95"), ("R-Q01", "3")], 1)
        ],
    )
    for n, status in enumerate(
        ["PLANNED", "ARRIVED", "INSPECTED", "INSPECTED", "CANCELLED"], 1
    ):
        no = f"IN-{day:%Y%m%d}-{n:03d}"
        inspected = status == "INSPECTED"
        received = n == 3
        arrived = status in {"ARRIVED", "INSPECTED"}
        id = writer.add(
            "wms.inbound_notice",
            [
                {
                    "notice_no": no,
                    "business_key": f"DEMO-INBOUND-{n}",
                    "warehouse_id": houses["WH-RAW"],
                    "status": status,
                    "expected_on": day,
                    "vehicle_no": f"합성트럭-{n:02d}",
                    "partner_ref": "DEMO-SUPPLIER",
                    "version": 3 if inspected else 2 if status != "PLANNED" else 1,
                    "arrived_at": stamp - timedelta(hours=1) if arrived else None,
                    "inspected_at": stamp if inspected else None,
                    "cancelled_at": stamp if status == "CANCELLED" else None,
                    "stock_document_id": doc if received else None,
                    "reason": "운송 취소 예시" if status == "CANCELLED" else None,
                    "created_at": stamp - timedelta(days=1),
                    "updated_at": stamp,
                }
            ],
            "notice_no",
        )[no]
        writer.add(
            "wms.inbound_notice_line",
            [
                {
                    "notice_id": id,
                    "line_no": 1,
                    "item_id": items["RM-PBT"],
                    "expected_qty": Decimal(100),
                    "accepted_qty": Decimal("95" if received else "0")
                    if inspected
                    else None,
                    "quarantined_qty": Decimal("3" if received else "0")
                    if inspected
                    else None,
                    "shortage_qty": Decimal("2" if received else "100")
                    if inspected
                    else None,
                    "normal_location_id": locations["R-A01"],
                    "quarantine_location_id": locations["R-Q01"],
                    "reason": "외관 이물·운송 부족 예시"
                    if received
                    else "전량 미도착 예시"
                    if inspected
                    else None,
                    "created_at": stamp - timedelta(days=1),
                }
            ],
        )
    # The new template records a consumed reservation alongside an existing historical
    # shipment. It does not add a second ledger deduction or consume SH-0004.
    table = writer.table("wms.stock_document")
    shipped = (
        writer.connection.execute(
            select(table)
            .where(
                table.c.workspace_id == writer.workspace_id,
                table.c.generation_id == writer.generation_id,
                table.c.document_type == "ERP_SHIPMENT",
            )
            .order_by(table.c.id)
        )
        .mappings()
        .first()
    )
    assert shipped is not None
    move_table = writer.table("wms.stock_move")
    moves = (
        writer.connection.execute(
            select(move_table)
            .where(
                move_table.c.workspace_id == writer.workspace_id,
                move_table.c.generation_id == writer.generation_id,
                move_table.c.document_id == shipped["id"],
            )
            .order_by(move_table.c.line_no)
        )
        .mappings()
        .all()
    )
    for n, status in enumerate(["ACTIVE", "RELEASED", "CONSUMED"], 1):
        no = f"RSV-{day:%Y%m%d}-{n:03d}"
        used = status == "CONSUMED"
        closed = (
            shipped["posted_at"] if used else stamp if status == "RELEASED" else None
        )
        created = (closed or stamp) - timedelta(hours=1)
        id = writer.add(
            "wms.stock_reservation",
            [
                {
                    "reservation_no": no,
                    "business_key": f"DEMO-RESERVATION-{n}",
                    "status": status,
                    "version": 1 if status == "ACTIVE" else 2,
                    "reason": "고객 일정 변경 예시" if status == "RELEASED" else None,
                    "closed_at": closed,
                    "shipment_source_key": shipped["source_key"] if used else None,
                    "stock_document_id": shipped["id"] if used else None,
                    "created_at": created,
                }
            ],
            "reservation_no",
        )[no]
        lines = (
            [
                {
                    "item_id": m["item_id"],
                    "location_id": m["location_id"],
                    "lot_no": m["lot_no"],
                    "quantity": -m["qty_delta"],
                }
                for m in moves
            ]
            if used
            else [
                {
                    "item_id": items["RM-PBT"],
                    "location_id": locations["R-A01"],
                    "lot_no": None,
                    "quantity": Decimal("40" if status == "ACTIVE" else "10"),
                }
            ]
        )
        writer.add(
            "wms.stock_reservation_line",
            [
                {**line, "reservation_id": id, "line_no": index, "created_at": created}
                for index, line in enumerate(lines, 1)
            ],
        )
