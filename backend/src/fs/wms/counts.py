"""W2b-1f 재고 실사(W-14)·재고 마감(W-15) 업무 규칙 (DSN-13 F35·F39, Q6).

- 실사를 시작하면 그 시점의 장부 수량(원장 합계)을 count_line에 스냅샷으로 굳힌다.
  차이 = 실사 − 장부는 저장하지 않고 조회할 때 계산한다.
- OPEN 동안 대상 위치의 재고 이동을 막는다(실사 잠금). 막는 곳은
  service._guard_stock_writable 한 곳이며, 여기서는 행만 만든다.
- 조정은 차이가 있는 행만 CYCLE_COUNT 전표로 반영한다. 차이가 없으면 전표 없이 ADJUSTED.
- 마감한 달(stock_period.status='closed')에는 재고 전표를 만들 수 없다. 같은 길목에서 막는다.
"""

from decimal import Decimal
from typing import Any

from fs.common.scope import read_scope
from fs.wms import receiving as rec
from fs.wms import service as base

S = base._S
q = rec._query


def _num(value: Any) -> str:
    return f"{Decimal(str(value)):.3f}"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _header(c, scoped, row_id: int, lock: bool = False) -> dict[str, Any]:
    found = (
        q(
            c,
            scoped,
            f"SELECT * FROM wms.count_order WHERE {S} AND id=:id"
            + (" FOR UPDATE" if lock else ""),
            id=row_id,
        )
        .mappings()
        .first()
    )
    if found is None:
        raise base._not_found("재고 실사")
    return dict(found)


def _lines(c, scoped, order_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not order_ids:
        return {}
    rows = q(
        c,
        scoped,
        f"""
        SELECT cl.id, cl.count_order_id, cl.location_id, cl.item_id, cl.lot_no,
               cl.book_qty, cl.counted_qty, cl.counted_at,
               loc.code AS location_code, loc.name AS location_name,
               i.item_code, i.name AS item_name, i.base_unit
        FROM wms.count_line cl
        JOIN wms.storage_location loc
          ON loc.workspace_id=cl.workspace_id AND loc.generation_id=cl.generation_id
         AND loc.id=cl.location_id
        JOIN wms.item i
          ON i.workspace_id=cl.workspace_id AND i.generation_id=cl.generation_id AND i.id=cl.item_id
        WHERE cl.{S.replace(" AND ", " AND cl.")}
          AND cl.count_order_id = ANY(:ids)
        ORDER BY cl.count_order_id, loc.code, i.item_code, cl.lot_no NULLS FIRST
        """,
        ids=order_ids,
    ).mappings()
    out: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        counted = r["counted_qty"]
        out.setdefault(r["count_order_id"], []).append(
            {
                "id": r["id"],
                "locationId": r["location_id"],
                "locationCode": r["location_code"],
                "locationName": r["location_name"],
                "itemId": r["item_id"],
                "itemCode": r["item_code"],
                "itemName": r["item_name"],
                "baseUnit": r["base_unit"],
                "lotNo": r["lot_no"],
                "bookQty": _num(r["book_qty"]),
                "countedQty": None if counted is None else _num(counted),
                # 차이는 저장하지 않는다(F35). 실사 입력이 없으면 아직 차이가 없다.
                "diffQty": (
                    None
                    if counted is None
                    else _num(Decimal(str(counted)) - Decimal(str(r["book_qty"])))
                ),
                "countedAt": _iso(r["counted_at"]),
            }
        )
    return out


_SELECT = f"""
SELECT co.*, w.code AS warehouse_code, w.name AS warehouse_name,
       d.document_no AS stock_document_no
FROM wms.count_order co
JOIN wms.warehouse w
  ON w.workspace_id=co.workspace_id AND w.generation_id=co.generation_id AND w.id=co.warehouse_id
LEFT JOIN wms.stock_document d
  ON d.workspace_id=co.workspace_id AND d.generation_id=co.generation_id AND d.id=co.stock_document_id
WHERE co.{S.replace(" AND ", " AND co.")}
"""


def _enrich(c, scoped, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    line_map = _lines(c, scoped, [r["id"] for r in rows])
    out = []
    for r in rows:
        lines = line_map.get(r["id"], [])
        diffs = [line for line in lines if line["diffQty"] not in (None, "0.000")]
        out.append(
            {
                "id": r["id"],
                "countNo": r["count_no"],
                "kind": r["kind"],
                "warehouseId": r["warehouse_id"],
                "warehouseCode": r["warehouse_code"],
                "warehouseName": r["warehouse_name"],
                "status": r["status"],
                "snapshotAt": _iso(r["snapshot_at"]),
                "adjustedAt": _iso(r["adjusted_at"]),
                "stockDocumentId": r["stock_document_id"],
                "stockDocumentNo": r.get("stock_document_no"),
                "createdAt": _iso(r["created_at"]),
                "lineCount": len(lines),
                "countedCount": sum(1 for x in lines if x["countedQty"] is not None),
                "diffCount": len(diffs),
                "lines": lines,
            }
        )
    return out


def _detail(c, scoped, row_id: int) -> dict[str, Any]:
    rows = [
        dict(r) for r in q(c, scoped, _SELECT + " AND co.id=:id", id=row_id).mappings()
    ]
    if not rows:
        raise base._not_found("재고 실사")
    return _enrich(c, scoped, rows)[0]


def get_count_order(context: base.AuthContext, id: int) -> dict[str, Any]:
    with base._read() as c:
        return _detail(c, read_scope(c, context, base.MODULE), id)


def list_count_orders(
    context: base.AuthContext,
    status: str | None = None,
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        where, params = "", {}
        if status:
            where += " AND co.status=:status"
            params["status"] = status
        if warehouse_id:
            where += " AND co.warehouse_id=:warehouse_id"
            params["warehouse_id"] = warehouse_id
        total = q(
            c, scoped, "SELECT count(*) FROM (" + _SELECT + where + ") t", **params
        ).scalar_one()
        rows = [
            dict(r)
            for r in q(
                c,
                scoped,
                _SELECT + where + " ORDER BY co.id DESC LIMIT :limit OFFSET :offset",
                limit=page_size,
                offset=(page - 1) * page_size,
                **params,
            ).mappings()
        ]
        return {
            "rows": _enrich(c, scoped, rows),
            "total": total,
            "page": page,
            "pageSize": page_size,
        }


def create_count_order(
    context: base.AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        warehouse_id = int(values["warehouse_id"])
        wh = (
            q(
                c,
                scoped,
                f"SELECT id, is_active FROM wms.warehouse WHERE {S} AND id=:id",
                id=warehouse_id,
            )
            .mappings()
            .first()
        )
        if wh is None or not wh["is_active"]:
            rec._fail("warehouseId", "사용 중인 창고를 선택해 주세요.")

        open_count = q(
            c,
            scoped,
            f"SELECT count_no FROM wms.count_order WHERE {S} AND warehouse_id=:id AND status='OPEN'",
            id=warehouse_id,
        ).first()
        if open_count:
            raise base._conflict(
                f"이 창고에 진행 중인 실사({open_count[0]})가 있습니다.",
                "COUNT_IN_PROGRESS",
                countNo=open_count[0],
            )

        location_ids = values.get("location_ids") or None
        if location_ids is not None and not location_ids:
            location_ids = None
        snapshot = q(
            c,
            scoped,
            f"""
            SELECT m.location_id, m.item_id, m.lot_no, SUM(m.qty_delta) AS book_qty
            FROM wms.stock_move m
            JOIN wms.stock_document d
              ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id
            JOIN wms.storage_location loc
              ON loc.workspace_id=m.workspace_id AND loc.generation_id=m.generation_id
             AND loc.id=m.location_id
            WHERE m.{S.replace(" AND ", " AND m.")}
              AND d.status='posted'
              AND loc.warehouse_id=:warehouse_id
              AND (CAST(:ids AS bigint[]) IS NULL OR loc.id = ANY(CAST(:ids AS bigint[])))
            GROUP BY m.location_id, m.item_id, m.lot_no
            HAVING SUM(m.qty_delta) > 0
            """,
            warehouse_id=warehouse_id,
            ids=location_ids,
        ).mappings()
        rows = list(snapshot)
        if not rows:
            raise base._conflict(
                "실사할 재고가 없습니다.", "NO_STOCK", warehouseId=warehouse_id
            )

        now = rec._now(c)
        stem = f"CT-{now.astimezone(base.SEOUL):%Y%m%d}-"
        used = q(
            c,
            scoped,
            f"SELECT count(*) FROM wms.count_order WHERE {S} AND count_no LIKE :stem",
            stem=stem + "%",
        ).scalar_one()
        order_id = q(
            c,
            scoped,
            "INSERT INTO wms.count_order(workspace_id,generation_id,count_no,kind,warehouse_id,"
            "snapshot_at,status,created_at) VALUES(:w,:g,:no,:kind,:wh,:now,'OPEN',:now) RETURNING id",
            no=f"{stem}{used + 1:03d}",
            kind=values.get("kind") or "FULL",
            wh=warehouse_id,
            now=now,
        ).scalar_one()
        for r in rows:
            q(
                c,
                scoped,
                "INSERT INTO wms.count_line(workspace_id,generation_id,count_order_id,location_id,"
                "item_id,lot_no,book_qty,created_at) VALUES(:w,:g,:o,:loc,:item,:lot,:qty,:now)",
                o=order_id,
                loc=r["location_id"],
                item=r["item_id"],
                lot=r["lot_no"],
                qty=r["book_qty"],
                now=now,
            )
        return _detail(c, scoped, order_id), "count_order", order_id

    return base._action(context, "wms.count.create", key, values, fn)


def count_lines(
    context: base.AuthContext, id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        row = _header(c, scoped, id, lock=True)
        if row["status"] not in ("OPEN", "COUNTED"):
            raise base._conflict("이미 처리된 재고 실사입니다.", "INVALID_STATE")
        now = rec._now(c)
        for item in values["lines"]:
            updated = q(
                c,
                scoped,
                f"UPDATE wms.count_line SET counted_qty=:qty, counted_at=:now "
                f"WHERE {S} AND id=:id AND count_order_id=:o",
                qty=item["counted_qty"],
                now=now,
                id=int(item["line_id"]),
                o=id,
            ).rowcount
            if not updated:
                rec._fail(
                    "lines", f"실사 명세 {item['line_id']}을(를) 찾을 수 없습니다."
                )
        remaining = q(
            c,
            scoped,
            f"SELECT count(*) FROM wms.count_line WHERE {S} AND count_order_id=:o AND counted_qty IS NULL",
            o=id,
        ).scalar_one()
        if not remaining:
            q(
                c,
                scoped,
                f"UPDATE wms.count_order SET status='COUNTED' WHERE {S} AND id=:id",
                id=id,
            )
        return _detail(c, scoped, id), "count_order", id

    return base._action(context, f"wms.count.count:{id}", key, values, fn)


def adjust_count_order(
    context: base.AuthContext, id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        row = _header(c, scoped, id, lock=True)
        if row["status"] != "COUNTED":
            raise base._conflict(
                "모든 명세를 실사한 뒤에 조정할 수 있습니다.", "INVALID_STATE"
            )
        detail = _detail(c, scoped, id)
        moves = [
            {
                "item_id": line["itemId"],
                "location_id": line["locationId"],
                "lot_no": line["lotNo"],
                "qty_delta": Decimal(line["diffQty"]),
                "source_qty": None,
                "source_unit": None,
            }
            for line in detail["lines"]
            if line["diffQty"] not in (None, "0.000")
        ]
        now = rec._now(c)
        doc_id = None
        if moves:
            # 실사 잠금은 OPEN에만 걸리므로(COUNTED 상태) 자기 조정 전표는 통과한다.
            doc_id = base._insert_document(
                c,
                scoped,
                {
                    "document_type": "CYCLE_COUNT",
                    "status": "posted",
                    "source_key": None,
                    "source_ref": row["count_no"],
                    "document_on": now.astimezone(base.SEOUL).date(),
                    "posted_at": now,
                },
                moves,
                now.isoformat(),
            )
        q(
            c,
            scoped,
            f"UPDATE wms.count_order SET status='ADJUSTED', adjusted_at=:now, stock_document_id=:doc "
            f"WHERE {S} AND id=:id",
            now=now,
            doc=doc_id,
            id=id,
        )
        return _detail(c, scoped, id), "count_order", id

    return base._action(context, f"wms.count.adjust:{id}", key, values, fn)


def cancel_count_order(
    context: base.AuthContext, id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        row = _header(c, scoped, id, lock=True)
        if row["status"] in ("ADJUSTED", "CANCELLED"):
            raise base._conflict("이미 처리된 재고 실사입니다.", "INVALID_STATE")
        q(
            c,
            scoped,
            f"UPDATE wms.count_order SET status='CANCELLED' WHERE {S} AND id=:id",
            id=id,
        )
        return _detail(c, scoped, id), "count_order", id

    return base._action(context, f"wms.count.cancel:{id}", key, values, fn)


# ---- 재고 마감 (W-15, F39·Q6) ----


def list_periods(context: base.AuthContext) -> list[dict[str, Any]]:
    """전표가 있는 달과 마감 기록을 합쳐 보여 준다. 마감 행은 닫을 때 생긴다."""
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        rows = q(
            c,
            scoped,
            f"""
            SELECT m.period_month,
                   COALESCE(p.status, 'open') AS status,
                   p.closed_at,
                   m.document_count
            FROM (
                SELECT document_month AS period_month, count(*) AS document_count
                FROM wms.stock_document
                WHERE {S} AND status='posted'
                GROUP BY document_month
                UNION
                SELECT period_month, 0 FROM wms.stock_period WHERE {S}
            ) m
            LEFT JOIN wms.stock_period p
              ON p.workspace_id=:w AND p.generation_id=:g AND p.period_month=m.period_month
            ORDER BY m.period_month DESC
            """,
        ).mappings()
        seen: dict[str, dict[str, Any]] = {}
        for r in rows:
            month = r["period_month"]
            found = seen.setdefault(
                month,
                {
                    "periodMonth": month,
                    "status": r["status"],
                    "closedAt": _iso(r["closed_at"]),
                    "documentCount": 0,
                },
            )
            found["documentCount"] += r["document_count"]
            if r["status"] == "closed":
                found["status"] = "closed"
                found["closedAt"] = _iso(r["closed_at"])
        return sorted(seen.values(), key=lambda x: x["periodMonth"], reverse=True)


def close_period(
    context: base.AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        month = values["period_month"]
        open_count = q(
            c,
            scoped,
            f"SELECT count_no FROM wms.count_order WHERE {S} AND status IN ('OPEN','COUNTED') LIMIT 1",
        ).first()
        if open_count:
            raise base._conflict(
                f"진행 중인 실사({open_count[0]})를 끝내고 마감하세요.",
                "COUNT_IN_PROGRESS",
                countNo=open_count[0],
            )
        drafts = q(
            c,
            scoped,
            f"SELECT count(*) FROM wms.stock_document WHERE {S} AND document_month=:m AND status='draft'",
            m=month,
        ).scalar_one()
        if drafts:
            raise base._conflict(
                f"{month}에 확정하지 않은 전표가 {drafts}건 있습니다.",
                "DRAFT_DOCUMENTS",
                periodMonth=month,
                draftCount=drafts,
            )
        now = rec._now(c)
        q(
            c,
            scoped,
            "INSERT INTO wms.stock_period(workspace_id,generation_id,period_month,status,closed_at,created_at) "
            "VALUES(:w,:g,:m,'closed',:now,:now) "
            "ON CONFLICT (workspace_id,generation_id,period_month) "
            "DO UPDATE SET status='closed', closed_at=:now",
            m=month,
            now=now,
        )
        return {"periodMonth": month, "status": "closed"}, "stock_period", 0

    return base._action(context, "wms.period.close", key, values, fn)


def reopen_period(
    context: base.AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        month = values["period_month"]
        q(
            c,
            scoped,
            f"UPDATE wms.stock_period SET status='open', closed_at=NULL WHERE {S} AND period_month=:m",
            m=month,
        )
        return {"periodMonth": month, "status": "open"}, "stock_period", 0

    return base._action(context, "wms.period.reopen", key, values, fn)


def guard_master(c, scoped, kind: str, id: int, all_history: bool = False) -> None:
    condition = {
        "warehouse": "co.warehouse_id=:id",
        "item": "cl.item_id=:id",
        "location": "cl.location_id=:id",
    }[kind]
    used = q(
        c,
        scoped,
        f"""
        SELECT count(*) FROM wms.count_order co
        LEFT JOIN wms.count_line cl
          ON cl.workspace_id=co.workspace_id AND cl.generation_id=co.generation_id
         AND cl.count_order_id=co.id
        WHERE co.{S.replace(" AND ", " AND co.")} AND {condition}
          {"" if all_history else "AND co.status NOT IN ('CANCELLED','ADJUSTED')"}
        """,
        id=id,
    ).scalar_one()
    if used:
        raise base._conflict(
            "재고 실사가 참조하고 있어 사용 안 함으로 바꿀 수 없습니다.",
            "REFERENCED_BY_OTHERS",
        )
