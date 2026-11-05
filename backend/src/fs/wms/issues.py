"""W2b-1e 생산 불출(W-13) 업무 규칙 (DSN-13 F25, Q4·Q5).

- 요청(wms.issue_request)은 MES 작업지시 번호를 **코드 문자열 스냅샷**으로만 보관한다.
  업무 스키마 간 FK를 두지 않는다(FS-013 §6).
- 도착 위치는 설계상 라인(location_type='LINE')이다. 시드에 LINE 칸이 없을 수 있어
  일반(NORMAL) 칸도 허용하고 화면에서 안내한다. 피킹의 SHIPPING 처리와 같은 방식이다.
- wms.issue_request_line에는 위치·LOT 칸이 없다. 그래서 LOT 배정은 저장하지 않고
  **불출 시점에 계산**한다. 목록·상세는 같은 규칙으로 미리보기만 돌려준다.
- 배정은 피킹과 같은 규칙을 그대로 쓴다: 보류(활성 lot_hold·QMS 보류·status='HOLD')와
  만료(expiry_date < 업무 기준일·status='EXPIRED')를 빼고 FEFO → FIFO → 위치 코드 순.
"""

from decimal import Decimal
from typing import Any

from fs.common.clock import business_today
from fs.common.scope import read_scope
from fs.qms import interface as qms
from fs.wms import picks
from fs.wms import receiving as rec
from fs.wms import service as base

S = base._S
q = rec._query

# 예약·피킹 선점을 모두 빼고 가용 재고를 구한다. 생산 불출은 예약에 묶이지 않는다.
_NO_RESERVATION = -1


def _num(value: Any) -> str:
    return f"{Decimal(str(value)):.3f}"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _next_no(c, scoped, now) -> str:
    stem = f"IR-{now.astimezone(base.SEOUL):%Y%m%d}-"
    used = q(
        c,
        scoped,
        f"SELECT count(*) FROM wms.issue_request WHERE {S} AND request_no LIKE :stem",
        stem=stem + "%",
    ).scalar_one()
    return f"{stem}{used + 1:03d}"


def _header(c, scoped, row_id: int, lock: bool = False) -> dict[str, Any]:
    found = (
        q(
            c,
            scoped,
            f"SELECT * FROM wms.issue_request WHERE {S} AND id=:id"
            + (" FOR UPDATE" if lock else ""),
            id=row_id,
        )
        .mappings()
        .first()
    )
    if found is None:
        raise base._not_found("생산 불출 요청을 찾을 수 없습니다.")
    return dict(found)


def _lines(c, scoped, request_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not request_ids:
        return {}
    rows = q(
        c,
        scoped,
        f"""
        SELECT rl.id, rl.issue_request_id, rl.line_no, rl.item_id, rl.qty, rl.issued_qty,
               i.item_code, i.name AS item_name, i.base_unit
        FROM wms.issue_request_line rl
        JOIN wms.item i
          ON i.workspace_id=rl.workspace_id AND i.generation_id=rl.generation_id AND i.id=rl.item_id
        WHERE rl.{S.replace(" AND ", " AND rl.")}
          AND rl.issue_request_id = ANY(:ids)
        ORDER BY rl.issue_request_id, rl.line_no
        """,
        ids=request_ids,
    ).mappings()
    out: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["issue_request_id"], []).append(
            {
                "id": r["id"],
                "lineNo": r["line_no"],
                "itemId": r["item_id"],
                "itemCode": r["item_code"],
                "itemName": r["item_name"],
                "baseUnit": r["base_unit"],
                "qty": _num(r["qty"]),
                "issuedQty": None if r["issued_qty"] is None else _num(r["issued_qty"]),
            }
        )
    return out


def _allocate(
    c, scoped, warehouse_id: int, wants: list[tuple[int, Decimal]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """FEFO → FIFO로 LOT을 배정한다. (배정 목록, 부족 목록)을 돌려준다.

    위치·LOT을 저장하지 않으므로 미리보기와 확정이 같은 함수를 쓴다.
    """
    item_ids = sorted({item_id for item_id, _ in wants})
    lot_map = picks._lot_metadata(c, scoped, item_ids)
    qms_held = set(qms.held_lot_nos(c, scoped) or ())
    today = business_today()
    buckets = [
        b
        for b in picks._candidate_buckets(c, scoped, _NO_RESERVATION, item_ids, lot_map)
        if b["warehouse_id"] == warehouse_id
        and picks._lot_block_reason(b["item_id"], b["lot_no"], lot_map, qms_held, today)
        is None
    ]
    buckets.sort(key=picks._fefo_fifo_key)

    allocated: list[dict[str, Any]] = []
    short: list[dict[str, Any]] = []
    for item_id, want in wants:
        left = want
        for b in buckets:
            if left <= 0:
                break
            if b["item_id"] != item_id or b["avail"] <= 0:
                continue
            take = min(left, b["avail"])
            b["avail"] -= take
            left -= take
            allocated.append(
                {
                    "itemId": item_id,
                    "locationId": b["location_id"],
                    "locationCode": b["location_code"],
                    "locationName": b["location_name"],
                    "lotNo": b["lot_no"],
                    "qty": _num(take),
                    "_qty": take,
                }
            )
        if left > 0:
            available = want - left
            short.append(
                {
                    "itemId": item_id,
                    "requestedQty": _num(want),
                    "availableQty": _num(available),
                    "shortageQty": _num(left),
                }
            )
    return allocated, short


def _enrich(c, scoped, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    line_map = _lines(c, scoped, [r["id"] for r in rows])
    out = []
    for r in rows:
        lines = line_map.get(r["id"], [])
        row = {
            "id": r["id"],
            "requestNo": r["request_no"],
            "workOrderNo": r["work_order_no"],
            "lineLocationId": r["line_location_id"],
            "lineLocationCode": r.get("line_location_code"),
            "lineLocationName": r.get("line_location_name"),
            "lineLocationType": r.get("line_location_type"),
            "warehouseId": r.get("warehouse_id"),
            "warehouseCode": r.get("warehouse_code"),
            "warehouseName": r.get("warehouse_name"),
            "status": r["status"],
            "neededAt": _iso(r["needed_at"]),
            "issuedAt": _iso(r["issued_at"]),
            "stockDocumentId": r["stock_document_id"],
            "stockDocumentNo": r.get("stock_document_no"),
            "cancelReason": r["cancel_reason"],
            "createdAt": _iso(r["created_at"]),
            "lineCount": len(lines),
            "lines": lines,
        }
        if r["status"] == "OPEN" and lines:
            wants = [(line["itemId"], Decimal(line["qty"])) for line in lines]
            allocated, short = _allocate(c, scoped, r["warehouse_id"], wants)
            row["allocationPreview"] = [
                {k: v for k, v in a.items() if k != "_qty"} for a in allocated
            ]
            row["shortages"] = short
        else:
            row["allocationPreview"] = []
            row["shortages"] = []
        out.append(row)
    return out


_SELECT = f"""
SELECT r.*, loc.code AS line_location_code, loc.name AS line_location_name,
       loc.location_type AS line_location_type, loc.warehouse_id,
       w.code AS warehouse_code, w.name AS warehouse_name,
       d.document_no AS stock_document_no
FROM wms.issue_request r
JOIN wms.storage_location loc
  ON loc.workspace_id=r.workspace_id AND loc.generation_id=r.generation_id AND loc.id=r.line_location_id
JOIN wms.warehouse w
  ON w.workspace_id=loc.workspace_id AND w.generation_id=loc.generation_id AND w.id=loc.warehouse_id
LEFT JOIN wms.stock_document d
  ON d.workspace_id=r.workspace_id AND d.generation_id=r.generation_id AND d.id=r.stock_document_id
WHERE r.{S.replace(" AND ", " AND r.")}
"""


def _detail(c, scoped, row_id: int) -> dict[str, Any]:
    rows = [
        dict(r) for r in q(c, scoped, _SELECT + " AND r.id=:id", id=row_id).mappings()
    ]
    if not rows:
        raise base._not_found("생산 불출 요청을 찾을 수 없습니다.")
    return _enrich(c, scoped, rows)[0]


def get_issue_request(context: base.AuthContext, id: int) -> dict[str, Any]:
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        return _detail(c, scoped, id)


def list_issue_requests(
    context: base.AuthContext,
    status: str | None = None,
    warehouse_id: int | None = None,
    work_order_no: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        where, params = "", {}
        if status:
            where += " AND r.status=:status"
            params["status"] = status
        if warehouse_id:
            where += " AND loc.warehouse_id=:warehouse_id"
            params["warehouse_id"] = warehouse_id
        if work_order_no:
            where += " AND r.work_order_no=:work_order_no"
            params["work_order_no"] = work_order_no
        total = q(
            c,
            scoped,
            "SELECT count(*) FROM (" + _SELECT + where + ") t",
            **params,
        ).scalar_one()
        rows = [
            dict(r)
            for r in q(
                c,
                scoped,
                _SELECT + where + " ORDER BY r.id DESC LIMIT :limit OFFSET :offset",
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


def _line_location(c, scoped, location_id: int) -> dict[str, Any]:
    loc = base._location(c, scoped, location_id)
    if (
        loc is None
        or not loc["isActive"]
        or loc["locationType"] not in ("LINE", "NORMAL")
    ):
        rec._fail(
            "lineLocationId",
            "라인(LINE) 또는 일반(NORMAL) 유형의 활성 위치를 선택해 주세요.",
        )
    return loc


def create_issue_request(
    context: base.AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        loc = _line_location(c, scoped, int(values["line_location_id"]))
        lines = values["lines"]
        seen: set[int] = set()
        for n, line in enumerate(lines, 1):
            item_id = int(line["item_id"])
            if item_id in seen:
                rec._fail("lines", f"{n}번째 자재: 같은 품목이 이미 있습니다.")
            seen.add(item_id)
            item = (
                q(
                    c,
                    scoped,
                    f"SELECT id, is_active FROM wms.item WHERE {S} AND id=:id",
                    id=item_id,
                )
                .mappings()
                .first()
            )
            if item is None:
                rec._fail("lines", f"{n}번째 자재: 유효하지 않은 품목입니다.")
            if not item["is_active"]:
                rec._fail("lines", f"{n}번째 자재: 사용하지 않는 품목입니다.")

        now = rec._now(c)
        request_no = _next_no(c, scoped, now)
        request_id = q(
            c,
            scoped,
            "INSERT INTO wms.issue_request(workspace_id,generation_id,request_no,work_order_no,"
            "line_location_id,needed_at,status,created_at) "
            "VALUES(:w,:g,:request_no,:work_order_no,:line_location_id,:needed_at,'OPEN',:now) RETURNING id",
            request_no=request_no,
            work_order_no=(values.get("work_order_no") or None),
            line_location_id=loc["id"],
            needed_at=(values.get("needed_at") or None),
            now=now,
        ).scalar_one()
        for n, line in enumerate(lines, 1):
            q(
                c,
                scoped,
                "INSERT INTO wms.issue_request_line(workspace_id,generation_id,issue_request_id,"
                "line_no,item_id,qty,created_at) VALUES(:w,:g,:id,:line_no,:item_id,:qty,:now)",
                id=request_id,
                line_no=n,
                item_id=int(line["item_id"]),
                qty=line["qty"],
                now=now,
            )
        return _detail(c, scoped, request_id), "issue_request", request_id

    return base._action(context, "wms.issue.create", key, values, fn)


def confirm_issue_request(
    context: base.AuthContext, id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        row = _header(c, scoped, id, lock=True)
        if row["status"] != "OPEN":
            raise base._conflict("이미 처리된 생산 불출 요청입니다.", "INVALID_STATE")
        detail = _detail(c, scoped, id)
        lines = detail["lines"]
        if not lines:
            raise base._conflict("생산 불출 명세가 없습니다.", "INVALID_STATE")

        wanted = values.get("lines")
        want_map = (
            {item["line_id"]: Decimal(str(item["issued_qty"])) for item in wanted}
            if wanted is not None
            else None
        )

        wants: list[tuple[int, Decimal]] = []
        issued: dict[int, Decimal] = {}
        for line in lines:
            ordered = Decimal(line["qty"])
            if want_map is not None:
                if line["id"] not in want_map:
                    rec._fail(
                        "lines", f"명세 #{line['lineNo']}의 불출 수량이 누락되었습니다."
                    )
                qty = want_map[line["id"]]
            else:
                qty = ordered
            if qty < Decimal(0) or qty > ordered:
                rec._fail(
                    "lines",
                    f"불출 수량은 0 이상, 요청 수량({ordered}) 이하여야 합니다.",
                )
            issued[line["id"]] = qty
            if qty > 0:
                wants.append((line["itemId"], qty))

        if not wants:
            rec._fail("lines", "최소 1개 이상의 자재를 불출해야 합니다.")

        allocated, short = _allocate(c, scoped, detail["warehouseId"], wants)
        if short:
            raise base._conflict(
                "가용 재고가 부족해 생산 불출을 확정할 수 없습니다.",
                "INSUFFICIENT_AVAILABLE",
                shortages=short,
            )

        to_location_id = detail["lineLocationId"]
        moves = []
        for a in allocated:
            if a["locationId"] == to_location_id:
                rec._fail(
                    "lineLocationId", "출발 위치와 다른 라인 위치를 선택해 주세요."
                )
            for location_id, delta in (
                (a["locationId"], -a["_qty"]),
                (to_location_id, a["_qty"]),
            ):
                moves.append(
                    {
                        "item_id": a["itemId"],
                        "location_id": location_id,
                        "lot_no": a["lotNo"],
                        "qty_delta": delta,
                        "source_qty": None,
                        "source_unit": None,
                    }
                )

        for line_id, qty in issued.items():
            q(
                c,
                scoped,
                f"UPDATE wms.issue_request_line SET issued_qty=:qty WHERE {S} AND id=:id",
                qty=qty,
                id=line_id,
            )

        now = rec._now(c)
        doc_id = base._insert_document(
            c,
            scoped,
            {
                "document_type": "PRODUCTION_ISSUE",
                "status": "posted",
                "source_key": None,
                "source_ref": row["request_no"],
                "document_on": now.astimezone(base.SEOUL).date(),
                "posted_at": now,
            },
            moves,
            now.isoformat(),
        )
        q(
            c,
            scoped,
            f"UPDATE wms.issue_request "
            f"SET status='ISSUED', issued_at=:now, stock_document_id=:doc_id, cancel_reason=NULL "
            f"WHERE {S} AND id=:id",
            now=now,
            doc_id=doc_id,
            id=id,
        )
        return _detail(c, scoped, id), "issue_request", id

    return base._action(context, f"wms.issue.confirm:{id}", key, values, fn)


def cancel_issue_request(
    context: base.AuthContext, id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        row = _header(c, scoped, id, lock=True)
        if row["status"] != "OPEN":
            raise base._conflict("이미 처리된 생산 불출 요청입니다.", "INVALID_STATE")
        reason = (values.get("cancel_reason") or "").strip()
        if not reason:
            rec._fail("cancelReason", "취소 사유를 입력해 주세요.")
        q(
            c,
            scoped,
            f"UPDATE wms.issue_request "
            f"SET status='CANCELLED', issued_at=NULL, stock_document_id=NULL, cancel_reason=:reason "
            f"WHERE {S} AND id=:id",
            reason=reason,
            id=id,
        )
        return _detail(c, scoped, id), "issue_request", id

    return base._action(context, f"wms.issue.cancel:{id}", key, values, fn)


def guard_master(c, scoped, kind: str, id: int, all_history: bool = False) -> None:
    condition = {
        "warehouse": "loc.warehouse_id=:id",
        "item": "rl.item_id=:id",
        "location": "r.line_location_id=:id",
    }[kind]
    used = q(
        c,
        scoped,
        f"""
        SELECT count(*) FROM wms.issue_request r
        JOIN wms.storage_location loc
          ON loc.workspace_id=r.workspace_id AND loc.generation_id=r.generation_id AND loc.id=r.line_location_id
        LEFT JOIN wms.issue_request_line rl
          ON rl.workspace_id=r.workspace_id AND rl.generation_id=r.generation_id AND rl.issue_request_id=r.id
        WHERE r.{S.replace(" AND ", " AND r.")} AND {condition}
          {"" if all_history else "AND r.status <> 'CANCELLED'"}
        """,
        id=id,
    ).scalar_one()
    if used:
        raise base._conflict(
            "생산 불출 요청이 참조하고 있어 사용 안 함으로 바꿀 수 없습니다.",
            "REFERENCED_BY_OTHERS",
        )
