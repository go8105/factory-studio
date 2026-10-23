# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""QMS API (/api/v1/qms, FS-023 모듈 설계 8장). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.qms import service
from fs.qms.schema import (
    CalibrationCreate,
    CapaCreate,
    CapaUpdate,
    CapaVerify,
    ChangeNoticeCreate,
    ChangeNoticeDecide,
    ChangeNoticeUpdate,
    ChangeNoticeVerify,
    DefectTypeCreate,
    DefectTypeUpdate,
    FirstArticleCreate,
    GaugeCreate,
    GaugeUpdate,
    HoldRelease,
    InspectionCreate,
    InspectionUpdate,
    NcrCreate,
    NcrUpdate,
    SpecCreate,
    SpecUpdate,
)

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]
MONTH = r"^[0-9]{4}-(0[1-9]|1[0-2])$"


# 공통 엔진: CSRF·멱등 키 확인
_mutation = mutation_key


def _values(
    payload: BaseModel, nullable: frozenset[str] = frozenset()
) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _data(value: Any) -> dict[str, Any]:
    return {"data": value}


# ---- 대시보드 ----
@router.get("/dashboard")
def get_dashboard(
    context: Auth, month: Annotated[str | None, Query(pattern=MONTH)] = None
):
    return _data(service.dashboard(context, month))


# ---- 불량 유형 (Q-06) ----
@router.get("/defect-types")
def list_defect_types(context: Auth):
    return _data(service.list_defect_types(context))


@router.post("/defect-types", status_code=201)
def create_defect_type(
    payload: DefectTypeCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_defect_type(
            context, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.patch("/defect-types/{row_id}")
def update_defect_type(
    row_id: int,
    payload: DefectTypeUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_defect_type(
            context, row_id, _values(payload), _mutation(context, csrf, key)
        )
    )


@router.delete("/defect-types/{row_id}")
def delete_defect_type(
    row_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(
        service.delete_defect_type(context, row_id, _mutation(context, csrf, key))
    )


# ---- 검사 기준 (Q-02) ----
@router.get("/inspection-specs")
def list_specs(
    context: Auth,
    item_code: Annotated[str | None, Query(alias="itemCode", max_length=40)] = None,
    status: Annotated[str | None, Query(pattern="^(draft|published|retired)$")] = None,
):
    return _data(service.list_specs(context, item_code, status))


@router.post("/inspection-specs", status_code=201)
def create_spec(
    payload: SpecCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_spec(
            context, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.get("/inspection-specs/{spec_id}")
def get_spec(spec_id: int, context: Auth):
    return _data(service.get_spec(context, spec_id))


@router.patch("/inspection-specs/{spec_id}")
def update_spec(
    spec_id: int,
    payload: SpecUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    values = payload.model_dump(exclude_unset=True)
    if values.get("items") is None:
        values.pop("items", None)
    return _data(
        service.update_spec(context, spec_id, values, _mutation(context, csrf, key))
    )


@router.delete("/inspection-specs/{spec_id}")
def delete_spec(
    spec_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(service.delete_spec(context, spec_id, _mutation(context, csrf, key)))


@router.post("/inspection-specs/{spec_id}/publish")
def publish_spec(
    spec_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(service.publish_spec(context, spec_id, _mutation(context, csrf, key)))


@router.post("/inspection-specs/{spec_id}/retire")
def retire_spec(
    spec_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(service.retire_spec(context, spec_id, _mutation(context, csrf, key)))


@router.post("/inspection-specs/{spec_id}/revise", status_code=201)
def revise_spec(
    spec_id: int, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(service.revise_spec(context, spec_id, _mutation(context, csrf, key)))


# ---- MES 조회 (Q-03, D9) ----
@router.get("/lookups/mes-lots")
def mes_lots(context: Auth, pending: bool = True):
    return _data(service.mes_lots(context, pending))


@router.get("/lookups/mes-items")
def mes_items(context: Auth):
    return _data(service.mes_items(context))


# ---- 검사 (Q-04) ----
@router.get("/inspections")
def list_inspections(
    context: Auth,
    status: Annotated[str | None, Query(pattern="^(draft|confirmed)$")] = None,
    result: Annotated[str | None, Query(pattern="^(PASS|FAIL)$")] = None,
    month: Annotated[str | None, Query(pattern=MONTH)] = None,
    lot_no: Annotated[str | None, Query(alias="lotNo", max_length=50)] = None,
):
    return _data(service.list_inspections(context, status, result, month, lot_no))


@router.post("/inspections", status_code=201)
def create_inspection(
    payload: InspectionCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_inspection(
            context, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: int, context: Auth):
    return _data(service.get_inspection(context, inspection_id))


@router.patch("/inspections/{inspection_id}")
def update_inspection(
    inspection_id: int,
    payload: InspectionUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    values = payload.model_dump(exclude_unset=True)
    return _data(
        service.update_inspection(
            context, inspection_id, values, _mutation(context, csrf, key)
        )
    )


@router.post("/inspections/{inspection_id}/confirm")
def confirm_inspection(
    inspection_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.confirm_inspection(
            context, inspection_id, _mutation(context, csrf, key)
        )
    )


@router.post("/inspections/{inspection_id}/reinspect", status_code=201)
def reinspect(
    inspection_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.reinspect(context, inspection_id, _mutation(context, csrf, key))
    )


@router.delete("/inspections/{inspection_id}")
def delete_inspection(
    inspection_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.delete_inspection(context, inspection_id, _mutation(context, csrf, key))
    )


# ---- 품질 보류 (Q-05) ----
@router.get("/holds")
def list_holds(
    context: Auth,
    status: Annotated[str | None, Query(pattern="^(held|released)$")] = None,
):
    return _data(service.list_holds(context, status))


@router.get("/holds/{hold_id}")
def get_hold(hold_id: int, context: Auth):
    return _data(service.get_hold(context, hold_id))


@router.post("/holds/{hold_id}/release")
def release_hold(
    hold_id: int,
    payload: HoldRelease,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.release_hold(
            context, hold_id, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


def _page(rows_total: tuple[list[dict[str, Any]], int], page: Page) -> dict[str, Any]:
    rows, total = rows_total
    return {
        "data": rows,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


# ---- 계측기·교정 (Q-11) ----
# 비워 둘 수 있는 칸 — 측정 범위·분해능은 모르면 비운다.
GAUGE_NULLABLE = frozenset({"measure_range", "resolution"})


@router.get("/gauges")
def list_gauges(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    status: Annotated[str | None, Query(pattern="^(ACTIVE|REPAIR|RETIRED)$")] = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.gauges(
            context,
            filters={"status": status},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/gauges", status_code=201)
def post_gauge(
    payload: GaugeCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_gauge(
            context, _values(payload, GAUGE_NULLABLE), _mutation(context, csrf, key)
        )
    )


@router.get("/gauges/{gauge_id}")
def get_gauge(gauge_id: int, context: Auth):
    return _data(service.gauge(context, gauge_id))


@router.patch("/gauges/{gauge_id}")
def patch_gauge(
    gauge_id: int,
    payload: GaugeUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_gauge(
            context,
            gauge_id,
            _values(payload, GAUGE_NULLABLE),
            _mutation(context, csrf, key),
        )
    )


@router.delete("/gauges/{gauge_id}", status_code=204)
def delete_gauge(
    gauge_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_gauge(context, gauge_id, _mutation(context, csrf, key))
    return Response(status_code=204)


@router.post("/gauges/{gauge_id}/calibrations", status_code=201)
def post_calibration(
    gauge_id: int,
    payload: CalibrationCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.add_calibration(
            context,
            gauge_id,
            payload.model_dump(),
            _mutation(context, csrf, key),
        )
    )


# ---- 4M 변경 (Q-12) ----
@router.get("/change-notices")
def list_change_notices(
    context: Auth,
    status: Annotated[
        str | None, Query(pattern="^(REQUESTED|APPROVED|REJECTED|VERIFIED)$")
    ] = None,
    change_type: Annotated[
        str | None, Query(alias="changeType", pattern="^(MAN|MACHINE|MATERIAL|METHOD)$")
    ] = None,
):
    return _data(service.list_change_notices(context, status, change_type))


@router.post("/change-notices", status_code=201)
def post_change_notice(
    payload: ChangeNoticeCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_change_notice(
            context,
            _values(payload, frozenset({"requested_on"})),
            _mutation(context, csrf, key),
        )
    )


@router.get("/change-notices/{cn_id}")
def get_change_notice(cn_id: int, context: Auth):
    return _data(service.get_change_notice(context, cn_id))


@router.patch("/change-notices/{cn_id}")
def patch_change_notice(
    cn_id: int,
    payload: ChangeNoticeUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_change_notice(
            context, cn_id, _values(payload), _mutation(context, csrf, key)
        )
    )


@router.post("/change-notices/{cn_id}/decision")
def decide_change_notice(
    cn_id: int,
    payload: ChangeNoticeDecide,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.decide_change_notice(
            context, cn_id, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.post("/change-notices/{cn_id}/first-article", status_code=201)
def post_first_article(
    cn_id: int,
    payload: FirstArticleCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_first_article(
            context,
            cn_id,
            _values(payload, frozenset({"inspected_on", "note"})),
            _mutation(context, csrf, key),
        )
    )


@router.post("/change-notices/{cn_id}/verification")
def verify_change_notice(
    cn_id: int,
    payload: ChangeNoticeVerify,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.verify_change_notice(
            context, cn_id, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


# ---- 부적합 보고 (Q-07) ----
# 비워 둘 수 있는 칸 — LOT·불량 유형·즉시 조치는 모르면 비운다.
NCR_NULLABLE = frozenset(
    {"lot_no", "defect_type_id", "immediate_action", "inspection_id", "source_ref"}
)


@router.get("/ncrs")
def list_ncrs(
    context: Auth,
    status: Annotated[str | None, Query(pattern="^(OPEN|CLOSED)$")] = None,
    origin: Annotated[
        str | None, Query(pattern="^(INCOMING|PROCESS|OUTGOING|CUSTOMER)$")
    ] = None,
):
    return _data(service.list_ncrs(context, status, origin))


@router.get("/ncrs/sources")
def ncr_sources(
    context: Auth,
    origin: Annotated[str, Query(pattern="^(INCOMING|PROCESS|OUTGOING)$")],
    month: Annotated[str | None, Query(pattern=MONTH)] = None,
):
    return _data(service.ncr_sources(context, origin, month))


@router.post("/ncrs", status_code=201)
def post_ncr(
    payload: NcrCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_ncr(
            context,
            _values(payload, NCR_NULLABLE | {"reported_on"}),
            _mutation(context, csrf, key),
        )
    )


@router.get("/ncrs/{ncr_id}")
def get_ncr(ncr_id: int, context: Auth):
    return _data(service.get_ncr(context, ncr_id))


@router.patch("/ncrs/{ncr_id}")
def patch_ncr(
    ncr_id: int,
    payload: NcrUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_ncr(
            context,
            ncr_id,
            _values(payload, NCR_NULLABLE),
            _mutation(context, csrf, key),
        )
    )


@router.post("/ncrs/{ncr_id}/closure")
def close_ncr(
    ncr_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(service.close_ncr(context, ncr_id, _mutation(context, csrf, key)))


# ---- 시정·예방 조치 (Q-08) ----
@router.get("/capas")
def list_capas(
    context: Auth,
    status: Annotated[
        str | None, Query(pattern="^(OPEN|DONE|VERIFIED|INEFFECTIVE)$")
    ] = None,
    ncr_id: Annotated[int | None, Query(alias="ncrId", gt=0)] = None,
):
    return _data(service.list_capas(context, status, ncr_id))


@router.post("/capas", status_code=201)
def post_capa(
    payload: CapaCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_capa(context, _values(payload), _mutation(context, csrf, key))
    )


@router.get("/capas/{capa_id}")
def get_capa(capa_id: int, context: Auth):
    return _data(service.get_capa(context, capa_id))


@router.patch("/capas/{capa_id}")
def patch_capa(
    capa_id: int,
    payload: CapaUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_capa(
            context, capa_id, _values(payload), _mutation(context, csrf, key)
        )
    )


@router.post("/capas/{capa_id}/completion")
def complete_capa(
    capa_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(service.complete_capa(context, capa_id, _mutation(context, csrf, key)))


@router.post("/capas/{capa_id}/verification")
def verify_capa(
    capa_id: int,
    payload: CapaVerify,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.verify_capa(
            context, capa_id, payload.model_dump(), _mutation(context, csrf, key)
        )
    )
