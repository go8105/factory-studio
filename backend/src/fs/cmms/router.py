# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""CMMS API (/api/v1/cmms, FS-029 · DSN-21). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from fs.cmms import service
from fs.cmms.schema import (
    AssetCreate,
    AssetImport,
    AssetUpdate,
    CancelBody,
    ChecklistItemBody,
    ChecksBody,
    FailureCodeCreate,
    FailureCodeUpdate,
    PartUsageCreate,
    PmPlanCreate,
    PmPlanUpdate,
    SignalConvert,
    SparePartCreate,
    SparePartUpdate,
    TechnicianCreate,
    TechnicianUpdate,
    VendorCreate,
    VendorUpdate,
    WorkLogCreate,
    WorkOrderComplete,
    WorkOrderCreate,
    WorkOrderStart,
)
from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.common.page import Page

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]

_mutation = mutation_key


def _values(
    payload: BaseModel, nullable: frozenset[str] = frozenset()
) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _page(rows_total: tuple[list[dict[str, Any]], int], page: Page) -> dict[str, Any]:
    rows, total = rows_total
    return {
        "data": rows,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


# 비워 둘 수 있는 칸 — 상세는 모르면 비운다. 상위 설비를 비우면 최상위가 된다.
ASSET_NULLABLE = frozenset(
    {
        "location",
        "parent_asset_id",
        "manufacturer",
        "model",
        "serial_no",
        "installed_on",
        "acquisition_cost",
        "criticality",
    }
)


# ── 설비 대장 (C-05) ────────────────────────────────────────────────────────


@router.get("/assets")
def list_assets(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    asset_type: Annotated[str | None, Query(alias="assetType")] = None,
    source: str | None = None,
    criticality: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.assets(
            context,
            filters={
                "assetType": asset_type,
                "source": source,
                "criticality": criticality,
                "active": active,
            },
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.get("/assets/tree")
def get_asset_tree(context: Auth):
    return {"data": service.asset_tree(context)}


@router.get("/assets/import-candidates")
def list_import_candidates(context: Auth, source: Annotated[str, Query()] = "MES"):
    return {"data": service.import_candidates(context, source)}


@router.post("/assets/import", status_code=201)
def post_asset_import(
    payload: AssetImport,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.import_assets(
            context,
            payload.source,
            payload.source_codes,
            _mutation(context, csrf, key),
        )
    }


@router.get("/assets/{asset_id}")
def get_asset(asset_id: int, context: Auth):
    return {"data": service.asset(context, asset_id)}


@router.post("/assets", status_code=201)
def post_asset(
    payload: AssetCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_asset(
            context, _values(payload, ASSET_NULLABLE), _mutation(context, csrf, key)
        )
    }


@router.patch("/assets/{asset_id}")
def patch_asset(
    asset_id: int,
    payload: AssetUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_asset(
            context,
            asset_id,
            _values(payload, ASSET_NULLABLE),
            _mutation(context, csrf, key),
        )
    }


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_asset(context, asset_id, _mutation(context, csrf, key))
    return Response(status_code=204)


# ── 고장 코드 (C-09) ────────────────────────────────────────────────────────


@router.get("/failure-codes")
def list_failure_codes(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    kind: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.failure_codes(
            context,
            filters={"kind": kind, "active": active},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/failure-codes", status_code=201)
def post_failure_code(
    payload: FailureCodeCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_failure_code(
            context,
            _values(payload, frozenset({"cause_category"})),
            _mutation(context, csrf, key),
        )
    }


@router.patch("/failure-codes/{code_id}")
def patch_failure_code(
    code_id: int,
    payload: FailureCodeUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_failure_code(
            context,
            code_id,
            _values(payload, frozenset({"cause_category"})),
            _mutation(context, csrf, key),
        )
    }


@router.delete("/failure-codes/{code_id}", status_code=204)
def delete_failure_code(
    code_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_failure_code(context, code_id, _mutation(context, csrf, key))
    return Response(status_code=204)


# ── 작업지시 (C-03) ─────────────────────────────────────────────────────────


@router.get("/work-orders")
def list_work_orders(
    context: Auth,
    status: str | None = None,
    kind: str | None = None,
    asset_id: Annotated[int | None, Query(alias="assetId")] = None,
):
    return {"data": service.work_orders(context, status, kind, asset_id)}


@router.get("/work-orders/{order_id}")
def get_work_order(order_id: int, context: Auth):
    return {"data": service.work_order(context, order_id)}


@router.post("/work-orders", status_code=201)
def post_work_order(
    payload: WorkOrderCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_work_order(
            context,
            _values(
                payload,
                frozenset(
                    {"description", "failure_at", "technician_id", "symptom_code_id"}
                ),
            ),
            _mutation(context, csrf, key),
        )
    }


@router.post("/work-orders/{order_id}/start")
def post_work_order_start(
    order_id: int,
    payload: WorkOrderStart,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.start_work_order(
            context,
            order_id,
            payload.model_dump(exclude_unset=True),
            _mutation(context, csrf, key),
        )
    }


@router.post("/work-orders/{order_id}/logs", status_code=201)
def post_work_log(
    order_id: int,
    payload: WorkLogCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.add_work_log(
            context,
            order_id,
            _values(payload, frozenset({"technician_id"})),
            _mutation(context, csrf, key),
        )
    }


@router.post("/work-orders/{order_id}/complete")
def post_work_order_complete(
    order_id: int,
    payload: WorkOrderComplete,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.complete_work_order(
            context,
            order_id,
            _values(
                payload,
                frozenset(
                    {"action_code_id", "restored_at", "vendor_id", "external_cost"}
                ),
            ),
            _mutation(context, csrf, key),
        )
    }


@router.post("/work-orders/{order_id}/cancel")
def post_work_order_cancel(
    order_id: int,
    payload: CancelBody,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.cancel_work_order(
            context, order_id, payload.reason, _mutation(context, csrf, key)
        )
    }


# ── 전환 대기 신호 (C-02) ───────────────────────────────────────────────────


@router.get("/signals")
def get_pending_signals(context: Auth):
    return {"data": service.pending_signals(context)}


@router.post("/signals/convert", status_code=201)
def post_signal_convert(
    payload: SignalConvert,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.convert_signal(
            context,
            _values(payload, frozenset({"title", "detected_at"})),
            _mutation(context, csrf, key),
        )
    }


# ── 정비원·외주 업체 (C-08) ─────────────────────────────────────────────────


@router.get("/technicians")
def list_technicians(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    skill: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.technicians(
            context,
            filters={"skill": skill, "active": active},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/technicians", status_code=201)
def post_technician(
    payload: TechnicianCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_technician(
            context,
            _values(payload, frozenset({"hr_employee_code"})),
            _mutation(context, csrf, key),
        )
    }


@router.patch("/technicians/{row_id}")
def patch_technician(
    row_id: int,
    payload: TechnicianUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_technician(
            context,
            row_id,
            _values(payload, frozenset({"hr_employee_code"})),
            _mutation(context, csrf, key),
        )
    }


@router.delete("/technicians/{row_id}", status_code=204)
def delete_technician(
    row_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_technician(context, row_id, _mutation(context, csrf, key))
    return Response(status_code=204)


@router.get("/vendors")
def list_vendors(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.vendors(
            context,
            filters={"active": active},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/vendors", status_code=201)
def post_vendor(
    payload: VendorCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_vendor(
            context,
            _values(payload, frozenset({"erp_partner_code", "phone"})),
            _mutation(context, csrf, key),
        )
    }


@router.patch("/vendors/{row_id}")
def patch_vendor(
    row_id: int,
    payload: VendorUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_vendor(
            context,
            row_id,
            _values(payload, frozenset({"erp_partner_code", "phone"})),
            _mutation(context, csrf, key),
        )
    }


@router.delete("/vendors/{row_id}", status_code=204)
def delete_vendor(
    row_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_vendor(context, row_id, _mutation(context, csrf, key))
    return Response(status_code=204)


@router.get("/lookups/hr-employees")
def lookup_hr_employees(context: Auth):
    return {"data": service.hr_employees(context)}


@router.get("/lookups/erp-partners")
def lookup_erp_partners(context: Auth):
    return {"data": service.erp_partners(context)}


# ── 예방보전 계획 (C-04) ────────────────────────────────────────────────────


@router.get("/pm-plans")
def list_pm_plans(
    context: Auth,
    asset_id: Annotated[int | None, Query(alias="assetId")] = None,
):
    return {"data": service.pm_plans(context, asset_id)}


@router.get("/pm-plans/{plan_id}")
def get_pm_plan(plan_id: int, context: Auth):
    return {"data": service.pm_plan(context, plan_id)}


@router.post("/pm-plans", status_code=201)
def post_pm_plan(
    payload: PmPlanCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_pm_plan(
            context,
            _values(
                payload, frozenset({"checklist", "interval_days", "interval_usage"})
            ),
            _mutation(context, csrf, key),
        )
    }


@router.patch("/pm-plans/{plan_id}")
def patch_pm_plan(
    plan_id: int,
    payload: PmPlanUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_pm_plan(
            context,
            plan_id,
            _values(
                payload, frozenset({"checklist", "interval_days", "interval_usage"})
            ),
            _mutation(context, csrf, key),
        )
    }


@router.post("/pm-plans/{plan_id}/items")
def post_checklist_item(
    plan_id: int,
    payload: ChecklistItemBody,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.save_checklist_item(
            context,
            plan_id,
            _values(
                payload,
                frozenset(
                    {"id", "standard_text", "lower_limit", "upper_limit", "unit"}
                ),
            ),
            _mutation(context, csrf, key),
        )
    }


@router.post("/pm-plans/{plan_id}/work-order", status_code=201)
def post_pm_work_order(
    plan_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_pm_work_order(
            context, plan_id, _mutation(context, csrf, key)
        )
    }


@router.post("/work-orders/{order_id}/checks")
def post_checks(
    order_id: int,
    payload: ChecksBody,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.save_checks(
            context,
            order_id,
            payload.model_dump(exclude_unset=True),
            _mutation(context, csrf, key),
        )
    }


@router.post("/work-orders/{order_id}/parts", status_code=201)
def post_part_usage(
    order_id: int,
    payload: PartUsageCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.add_part_usage(
            context,
            order_id,
            _values(payload, frozenset({"unit_cost"})),
            _mutation(context, csrf, key),
        )
    }


# ── 예비품 (C-06) ───────────────────────────────────────────────────────────


@router.get("/spare-parts")
def list_spare_parts(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.spare_parts(
            context,
            filters={"active": active},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/spare-parts", status_code=201)
def post_spare_part(
    payload: SparePartCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_spare_part(
            context,
            _values(payload, frozenset({"item_code", "unit_cost"})),
            _mutation(context, csrf, key),
        )
    }


@router.patch("/spare-parts/{row_id}")
def patch_spare_part(
    row_id: int,
    payload: SparePartUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_spare_part(
            context,
            row_id,
            _values(payload, frozenset({"item_code", "unit_cost"})),
            _mutation(context, csrf, key),
        )
    }


@router.delete("/spare-parts/{row_id}", status_code=204)
def delete_spare_part(
    row_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_spare_part(context, row_id, _mutation(context, csrf, key))
    return Response(status_code=204)


@router.get("/lookups/supply-items")
def lookup_supply_items(context: Auth):
    return {"data": service.supply_items(context)}


# ── 개요·지표·비용 (C-01·C-07·C-10) ────────────────────────────────────────

From = Annotated[date | None, Query(alias="from")]
To = Annotated[date | None, Query(alias="to")]


@router.get("/overview")
def get_overview(context: Auth):
    return {"data": service.overview(context)}


@router.get("/metrics")
def get_metrics(context: Auth, date_from: From = None, date_to: To = None):
    return {"data": service.metrics(context, date_from, date_to)}


@router.get("/cost")
def get_cost(context: Auth, date_from: From = None, date_to: To = None):
    return {"data": service.maintenance_cost(context, date_from, date_to)}
