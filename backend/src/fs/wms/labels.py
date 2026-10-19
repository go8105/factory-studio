"""W2b-1g 라벨 출력(W-17) 업무 규칙 (DSN-13 F07·F13).

- 위치 라벨(LOCATION)과 자재 LOT 라벨(MATERIAL_LOT)을 Code128로 브라우저에서 인쇄한다.
  인쇄 자체는 화면이 하고, 여기서는 **무엇을 몇 장 찍었는지**를 기록한다.
- `UK_PARTIAL`(종류·바코드당 VALID 1건)이 핵심이다. 같은 대상을 다시 찍으면
  이전 라벨을 VOID로 바꾸고 새 행이 `reprint_of_id`로 그것을 가리킨다.
  재발행에는 사유가 필요하다(c: reprint_of_id와 reprint_reason은 함께 있어야 한다).
"""

from typing import Any

from fs.common.scope import read_scope
from fs.wms import receiving as rec
from fs.wms import service as base

S = base._S
q = rec._query


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


_SELECT = f"""
SELECT lp.*, prev.barcode_value AS reprint_of_value, prev.printed_at AS reprint_of_printed_at
FROM wms.label_print lp
LEFT JOIN wms.label_print prev
  ON prev.workspace_id=lp.workspace_id AND prev.generation_id=lp.generation_id
 AND prev.id=lp.reprint_of_id
WHERE lp.{S.replace(" AND ", " AND lp.")}
"""


def _row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "labelKind": r["label_kind"],
        "barcodeValue": r["barcode_value"],
        "copies": r["copies"],
        "status": r["status"],
        "printedAt": _iso(r["printed_at"]),
        "reprintOfId": r["reprint_of_id"],
        "reprintOfValue": r.get("reprint_of_value"),
        "reprintReason": r["reprint_reason"],
        "createdAt": _iso(r["created_at"]),
    }


def list_labels(
    context: base.AuthContext,
    label_kind: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        where, params = "", {}
        if label_kind:
            where += " AND lp.label_kind=:kind"
            params["kind"] = label_kind
        if status:
            where += " AND lp.status=:status"
            params["status"] = status
        total = q(
            c, scoped, "SELECT count(*) FROM (" + _SELECT + where + ") t", **params
        ).scalar_one()
        rows = q(
            c,
            scoped,
            _SELECT + where + " ORDER BY lp.id DESC LIMIT :limit OFFSET :offset",
            limit=page_size,
            offset=(page - 1) * page_size,
            **params,
        ).mappings()
        return {
            "rows": [_row(dict(r)) for r in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }


def print_label(
    context: base.AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(c, scoped):
        kind = values["label_kind"]
        value = values["barcode_value"].strip()
        if not value:
            rec._fail("barcodeValue", "바코드 값을 입력해 주세요.")
        if kind == "LOCATION":
            found = q(
                c,
                scoped,
                f"SELECT 1 FROM wms.storage_location WHERE {S} AND code=:v AND is_active",
                v=value,
            ).first()
            if not found:
                rec._fail("barcodeValue", "사용 중인 위치 코드를 선택해 주세요.")
        else:
            found = q(
                c,
                scoped,
                f"SELECT 1 FROM wms.lot WHERE {S} AND lot_no=:v",
                v=value,
            ).first()
            if not found:
                rec._fail("barcodeValue", "등록된 LOT 번호를 선택해 주세요.")

        previous = (
            q(
                c,
                scoped,
                f"SELECT id FROM wms.label_print WHERE {S} "
                f"AND label_kind=:kind AND barcode_value=:v AND status='VALID' FOR UPDATE",
                kind=kind,
                v=value,
            )
            .mappings()
            .first()
        )
        reason = (values.get("reprint_reason") or "").strip() or None
        if previous is not None and not reason:
            raise base._conflict(
                "이미 발행한 라벨입니다. 재발행 사유를 적어 주세요.",
                "LABEL_EXISTS",
                labelId=previous["id"],
                barcodeValue=value,
            )
        if previous is None and reason:
            rec._fail("reprintReason", "처음 발행하는 라벨에는 사유를 적지 않습니다.")

        now = rec._now(c)
        if previous is not None:
            # 대상당 유효 라벨은 1건이다(UK_PARTIAL). 새 라벨을 넣기 전에 이전 것을 무효로 바꾼다.
            q(
                c,
                scoped,
                f"UPDATE wms.label_print SET status='VOID' WHERE {S} AND id=:id",
                id=previous["id"],
            )
        row_id = q(
            c,
            scoped,
            "INSERT INTO wms.label_print(workspace_id,generation_id,label_kind,barcode_value,"
            "copies,printed_at,status,reprint_of_id,reprint_reason,created_at) "
            "VALUES(:w,:g,:kind,:v,:copies,:now,'VALID',:prev,:reason,:now) RETURNING id",
            kind=kind,
            v=value,
            copies=int(values.get("copies") or 1),
            now=now,
            prev=previous["id"] if previous is not None else None,
            reason=reason,
        ).scalar_one()
        made = q(c, scoped, _SELECT + " AND lp.id=:id", id=row_id).mappings().first()
        return _row(dict(made)), "label_print", row_id

    return base._action(context, "wms.label.print", key, values, fn, 201)
