# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""WMS API (/api/v1/wms, FS-024 모듈 설계 8장). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.wms import receiving, reservations, service
from fs.wms.receiving_schema import (
    InspectionInput,
    NoticeCreate,
    NoticeKind,
    NoticeStatus,
    NoticeUpdate,
    PutawayComplete,
    ReasonInput,
    SourceLink,
    VersionInput,
)
from fs.wms.reservation_schema import (
    ConsumeShipment,
    ReservationCreate,
    ReservationStatus,
)
from fs.wms.schema import (
    ConversionCreate,
    DocumentCreate,
    DocumentUpdate,
    ItemCreate,
    ItemImport,
    ItemUpdate,
    LocationCreate,
    LocationType,
    LocationUpdate,
    LotCreate,
    LotHoldCreate,
    LotUpdate,
    ManualType,
    SourceKind,
    SourceSync,
    WarehouseCreate,
    WarehouseUpdate,
)

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]
MONTH = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
DocumentType = ManualType | SourceKind | Literal["WMS_INSPECTION", "PUTAWAY"] | None


# 공통 엔진: CSRF·멱등 키 확인
_mutation = mutation_key


def _values(
    payload: BaseModel, nullable: frozenset[str] = frozenset()
) -> dict[str, Any]:
    values = payload.model_dump(mode="json", exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _data(value: Any) -> dict[str, Any]:
    return {"data": value}


# ---- 대시보드 (W-01) ----
@router.get("/dashboard")
def get_dashboard(
    context: Auth, month: Annotated[str | None, Query(pattern=MONTH)] = None
):
    return _data(service.dashboard(context, month))


# ---- 창고·위치 (W-06) ----
@router.get("/warehouses")
def list_warehouses(context: Auth):
    return _data(service.list_warehouses(context))


@router.post("/warehouses", status_code=201)
def create_warehouse(
    payload: WarehouseCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_warehouse(
            context, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.patch("/warehouses/{row_id}")
def update_warehouse(
    row_id: int,
    payload: WarehouseUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_warehouse(
            context, row_id, _values(payload), _mutation(context, csrf, key)
        )
    )


@router.get("/warehouses/{warehouse_id}/locations")
def list_locations(warehouse_id: int, context: Auth):
    return _data(service.list_locations(context, warehouse_id))


@router.post("/warehouses/{warehouse_id}/locations", status_code=201)
def create_location(
    warehouse_id: int,
    payload: LocationCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_location(
            context, warehouse_id, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.patch("/locations/{row_id}")
def update_location(
    row_id: int,
    payload: LocationUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_location(
            context, row_id, _values(payload), _mutation(context, csrf, key)
        )
    )


@router.delete("/locations/{row_id}")
def delete_location(
    row_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(
        service.delete_location(context, row_id, _mutation(context, csrf, key))
    )


# ---- 품목·단위 (W-07) ----
@router.get("/items")
def list_items(context: Auth):
    return _data(service.list_items(context))


@router.post("/items", status_code=201)
def create_item(
    payload: ItemCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_item(
            context, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


NULLABLE_ITEM_FIELDS = frozenset(
    {
        "shelf_life_days",
        "storage_condition",
        "safety_stock",
        "max_stock",
        "abc_class",
        "plm_part_no",
        "plm_revision",
    }
)


@router.patch("/items/{row_id}")
def update_item(
    row_id: int,
    payload: ItemUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_item(
            context,
            row_id,
            _values(payload, nullable=NULLABLE_ITEM_FIELDS),
            _mutation(context, csrf, key),
        )
    )


@router.get("/lookups/mes-items")
def mes_items(context: Auth):
    return _data(service.mes_item_candidates(context))


@router.post("/items/import", status_code=201)
def import_items(
    payload: ItemImport,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.import_items(context, payload.item_codes, _mutation(context, csrf, key))
    )


@router.post("/items/{item_id}/conversions", status_code=201)
def add_conversion(
    item_id: int,
    payload: ConversionCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.add_conversion(
            context, item_id, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.delete("/items/{item_id}/conversions/{conversion_id}")
def delete_conversion(
    item_id: int,
    conversion_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.delete_conversion(
            context, item_id, conversion_id, _mutation(context, csrf, key)
        )
    )


# ---- LOT·보류 (W-10) ----
@router.get("/lots")
def list_lots(
    context: Auth,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    item_id: Annotated[int | None, Query(alias="itemId")] = None,
    lot_no: Annotated[str | None, Query(alias="lotNo", max_length=50)] = None,
    supplier_lot_no: Annotated[
        str | None, Query(alias="supplierLotNo", max_length=50)
    ] = None,
    status: Annotated[str | None, Query()] = None,
    keyword: Annotated[str | None, Query()] = None,
    expired_only: Annotated[bool, Query(alias="expiredOnly")] = False,
):
    page = Page(offset, limit).checked()
    rows, total = service.list_lots(
        context,
        page.offset,
        page.limit,
        {
            "item_id": item_id,
            "lot_no": lot_no,
            "supplier_lot_no": supplier_lot_no,
            "status": status,
            "keyword": keyword,
            "expired_only": expired_only,
        },
    )
    return {
        "data": rows,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/lots/{row_id}")
def get_lot(row_id: int, context: Auth):
    return _data(service.get_lot(context, row_id))


@router.post("/lots", status_code=201)
def create_lot(
    payload: LotCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_lot(context, payload.model_dump(), _mutation(context, csrf, key))
    )


@router.patch("/lots/{row_id}")
def update_lot(
    row_id: int,
    payload: LotUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_lot(
            context,
            row_id,
            _values(payload, nullable=service.NULLABLE_LOT_FIELDS),
            _mutation(context, csrf, key),
        )
    )


@router.post("/lots/{row_id}/hold", status_code=201)
def hold_lot(
    row_id: int,
    payload: LotHoldCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.hold_lot(
            context,
            row_id,
            payload.model_dump(),
            _mutation(context, csrf, key),
        )
    )


@router.post("/lots/{row_id}/release")
def release_lot(
    row_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.release_lot(
            context,
            row_id,
            _mutation(context, csrf, key),
        )
    )


# ---- 재고 현황·원장 (W-02·W-05) ----
@router.get("/stock")
def get_stock(
    context: Auth,
    item_code: Annotated[str | None, Query(alias="itemCode", max_length=40)] = None,
    warehouse_id: Annotated[int | None, Query(alias="warehouseId")] = None,
    lot_no: Annotated[str | None, Query(alias="lotNo", max_length=50)] = None,
    location_id: Annotated[int | None, Query(alias="locationId", gt=0)] = None,
    location_type: Annotated[LocationType | None, Query(alias="locationType")] = None,
    negative_only: Annotated[bool, Query(alias="negativeOnly")] = False,
    unassigned_only: Annotated[bool, Query(alias="unassignedOnly")] = False,
):
    return _data(
        service.stock(
            context,
            {
                "itemCode": item_code,
                "warehouseId": warehouse_id,
                "lotNo": lot_no,
                "locationId": location_id,
                "locationType": location_type,
                "negativeOnly": negative_only,
                "unassignedOnly": unassigned_only,
            },
        )
    )


@router.get("/moves")
def list_moves(
    context: Auth,
    item_code: Annotated[str | None, Query(alias="itemCode", max_length=40)] = None,
    lot_no: Annotated[str | None, Query(alias="lotNo", max_length=50)] = None,
    warehouse_id: Annotated[int | None, Query(alias="warehouseId")] = None,
    document_type: Annotated[DocumentType, Query(alias="type")] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
):
    return _data(
        service.moves(
            context,
            {
                "itemCode": item_code,
                "lotNo": lot_no,
                "warehouseId": warehouse_id,
                "type": document_type,
                "from": from_,
                "to": to,
            },
        )
    )


# ---- 원천 반영 (W-03) ----
@router.get("/sources")
def list_sources(
    context: Auth,
    kind: SourceKind,
    state: Annotated[str | None, Query(pattern="^(pending|synced|all)$")] = "pending",
):
    return _data(service.list_sources(context, kind, None if state == "all" else state))


@router.post("/sources/sync")
def sync_sources(
    payload: SourceSync,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.sync_sources(
            context, payload.kind, payload.source_keys, _mutation(context, csrf, key)
        )
    )


# ---- 재고 전표 (W-04) ----
@router.get("/documents")
def list_documents(
    context: Auth,
    document_type: Annotated[DocumentType | None, Query(alias="type")] = None,
    status: Annotated[str | None, Query(pattern="^(draft|posted)$")] = None,
    month: Annotated[str | None, Query(pattern=MONTH)] = None,
):
    return _data(
        service.list_documents(
            context, {"type": document_type, "status": status, "month": month}
        )
    )


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, context: Auth):
    return _data(service.get_document(context, doc_id))


@router.post("/documents", status_code=201)
def create_document(
    payload: DocumentCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_document(
            context, payload.model_dump(mode="json"), _mutation(context, csrf, key)
        )
    )


@router.patch("/documents/{doc_id}")
def update_document(
    doc_id: int,
    payload: DocumentUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    values = _values(payload, frozenset({"reason_code", "note", "document_on"}))
    return _data(
        service.update_document(context, doc_id, values, _mutation(context, csrf, key))
    )


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(
        service.delete_document(context, doc_id, _mutation(context, csrf, key))
    )


@router.post("/documents/{doc_id}/post")
def post_document(
    doc_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(service.post_document(context, doc_id, _mutation(context, csrf, key)))


# ---- 입고 예정·검수 (FS-026b1, TX-W4~W7) ----
@router.get("/inbound-notices")
def list_inbound_notices(
    context: Auth,
    status: NoticeStatus | None = None,
    warehouse_id: Annotated[int | None, Query(alias="warehouseId", gt=0)] = None,
    notice_kind: Annotated[NoticeKind | None, Query(alias="noticeKind")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
    expected_from: Annotated[date | None, Query(alias="expectedFrom")] = None,
    expected_to: Annotated[date | None, Query(alias="expectedTo")] = None,
):
    return _data(
        receiving.list_notices(
            context,
            status,
            warehouse_id,
            notice_kind,
            page,
            page_size,
            expected_from,
            expected_to,
        )
    )


@router.get("/inbound-notices/{row_id}")
def get_inbound_notice(row_id: int, context: Auth):
    return _data(receiving.get_notice(context, row_id))


@router.post("/inbound-notices", status_code=201)
def create_inbound_notice(
    payload: NoticeCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.create_notice(
            context, payload.model_dump(mode="json"), _mutation(context, csrf, key)
        )
    )


@router.patch("/inbound-notices/{row_id}")
def update_inbound_notice(
    row_id: int,
    payload: NoticeUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.update_notice(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.post("/inbound-notices/{row_id}/source-link")
def inbound_link_source(
    row_id: int,
    payload: SourceLink,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.link_source(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.post("/inbound-notices/{row_id}/source-unlink")
def inbound_unlink_source(
    row_id: int,
    payload: ReasonInput,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.unlink_source(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.post("/inbound-notices/{row_id}/arrive")
def inbound_arrive(
    row_id: int,
    payload: VersionInput,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.arrive(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.post("/inbound-notices/{row_id}/cancel")
def inbound_cancel(
    row_id: int,
    payload: ReasonInput,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.cancel(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.post("/inbound-notices/{row_id}/inspect")
def inbound_inspect_notice(
    row_id: int,
    payload: InspectionInput,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.inspect_notice(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


# ---- FS-026b2 reservations (TX-W8~W9) ----
@router.get("/reservations")
def list_reservations(
    context: Auth,
    status: ReservationStatus | None = None,
    item_code: Annotated[str | None, Query(alias="itemCode", max_length=40)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
    shortage_only: Annotated[bool, Query(alias="shortageOnly")] = False,
):
    return _data(
        reservations.list_reservations(
            context, status, item_code, page, page_size, shortage_only
        )
    )


@router.get("/reservations/{row_id}")
def get_reservation(row_id: int, context: Auth):
    return _data(reservations.get_reservation(context, row_id))


@router.post("/reservations", status_code=201)
def create_reservation(
    payload: ReservationCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        reservations.create_reservation(
            context, payload.model_dump(mode="json"), _mutation(context, csrf, key)
        )
    )


@router.post("/reservations/{row_id}/release")
def release_reservation(
    row_id: int,
    payload: ReasonInput,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        reservations.release(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.post("/reservations/{row_id}/consume-shipment")
def consume_reservation(
    row_id: int,
    payload: ConsumeShipment,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        reservations.consume(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.get("/reservation-sources")
def reservation_sources(context: Auth):
    return _data(reservations.sources(context))


@router.get("/reservations/{row_id}/shipment-preview")
def reservation_preview(
    row_id: int,
    context: Auth,
    source_key: Annotated[
        str, Query(alias="sourceKey", pattern=r"^ERP:SHIPMENT:.+$", max_length=100)
    ],
):
    return _data(reservations.shipment_preview(context, row_id, source_key))


# ---- 적치 작업 (W-11) ----
PutawayTaskStatus = Literal["OPEN", "DONE", "CANCELLED"]


@router.get("/putaway-tasks")
def list_putaway_tasks(
    context: Auth,
    status: PutawayTaskStatus | None = None,
    warehouse_id: Annotated[int | None, Query(alias="warehouseId")] = None,
    item_id: Annotated[int | None, Query(alias="itemId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
):
    return _data(
        receiving.list_putaway_tasks(
            context, status, warehouse_id, item_id, page, page_size
        )
    )


@router.post("/putaway-tasks/{row_id}/complete")
def complete_putaway_task(
    row_id: int,
    payload: PutawayComplete,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.complete_putaway_task(
            context,
            row_id,
            payload.model_dump(mode="json"),
            _mutation(context, csrf, key),
        )
    )


@router.post("/putaway-tasks/{row_id}/cancel")
def cancel_putaway_task(
    row_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        receiving.cancel_putaway_task(
            context,
            row_id,
            _mutation(context, csrf, key),
        )
    )
