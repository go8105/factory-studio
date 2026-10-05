"""FS-021 통합 검증 — SERVICE 정책 중 모듈을 가로지르는 두 가지.

1. 범위 격리(최우선): 다른 게스트 공간의 id로 FEMS·MES·ERP 자원을 읽거나 바꾸면 404이고 아무것도 바뀌지 않는다.
   같은 요청을 내 공간 id로 보내면 404가 아니다(경로가 틀려서 404인 것이 아님을 확인).
2. 멱등 키: 업무 모듈에서도 같은 키 + 같은 본문 = 같은 응답, 다른 본문 = 422, 24시간 지난 키 = 422.

나머지 정책(소명 한도·배정 한도·패킹 한도·설비 점유·매출 취소)은 모듈별 테스트에 동시성 주입과 함께 있다.
대응표는 docs/agent/통합검증_FS-021.md.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fs.main import create_app
from seed.copy import SCHEMAS, copy_module_seed
from sqlalchemy import text

# (메서드, 경로, 테이블, 본문). {id}는 대상 공간의 해당 테이블 첫 행.
CASES = [
    # FEMS
    ("GET", "/api/v1/fems/energy-sources/{id}", "fems.energy_source", None),
    ("GET", "/api/v1/fems/equipments/{id}", "fems.equipment", None),
    ("GET", "/api/v1/fems/meters/{id}", "fems.meter", None),
    ("GET", "/api/v1/fems/tariffs/{id}", "fems.tariff", None),
    ("GET", "/api/v1/fems/energy-factors/{id}", "fems.energy_factor", None),
    ("GET", "/api/v1/fems/production-records/{id}", "fems.production_record", None),
    ("PATCH", "/api/v1/fems/sites/{id}", "fems.site", {"name": "격리"}),
    ("PATCH", "/api/v1/fems/locations/{id}", "fems.location", {"name": "격리"}),
    (
        "POST",
        "/api/v1/fems/production-records/{id}/confirm",
        "fems.production_record",
        None,
    ),
    # MES
    ("GET", "/api/v1/mes/lots/{id}", "mes.lot", None),
    (
        "GET",
        "/api/v1/mes/executions/{id}/material-issues",
        "mes.operation_execution",
        None,
    ),
    ("POST", "/api/v1/mes/work-orders/{id}/release", "mes.work_order", None),
    (
        "POST",
        "/api/v1/mes/work-orders/{id}/cancel",
        "mes.work_order",
        {"cancelReason": "격리"},
    ),
    ("POST", "/api/v1/mes/production-plans/{id}/confirm", "mes.production_plan", None),
    ("POST", "/api/v1/mes/routes/{id}/revise", "mes.route_version", None),
    ("POST", "/api/v1/mes/packing-units/{id}/close", "mes.packing_unit", None),
    # ERP
    ("GET", "/api/v1/erp/partners/{id}", "erp.partner", None),
    ("GET", "/api/v1/erp/items/{id}", "erp.item", None),
    ("GET", "/api/v1/erp/partner-prices/{id}", "erp.partner_item_price", None),
    ("GET", "/api/v1/erp/accounts/{id}", "erp.account", None),
    ("PATCH", "/api/v1/erp/partners/{id}", "erp.partner", {"partnerName": "격리"}),
    ("GET", "/api/v1/erp/quotations/{id}/revisions", "erp.quotation", None),
    ("POST", "/api/v1/erp/quotations/{id}/revise", "erp.quotation", None),
    ("POST", "/api/v1/erp/sales-plans/{id}/confirm", "erp.sales_plan", None),
    ("POST", "/api/v1/erp/sales-orders/{id}/cancel", "erp.sales_order", None),
    (
        "POST",
        "/api/v1/erp/shipment-orders/{id}/cancel",
        "erp.shipment_order",
        {"reason": "격리"},
    ),
    (
        "POST",
        "/api/v1/erp/sales-records/{id}/cancel",
        "erp.sales_record",
        {"reason": "격리"},
    ),
    (
        "POST",
        "/api/v1/erp/tax-invoices/{id}/issue",
        "erp.tax_invoice",
        {"approvalNo": "ISO-1", "issuedOn": "2026-09-24"},
    ),
    ("POST", "/api/v1/erp/receipts/{id}/confirm", "erp.receipt", None),
    ("GET", "/api/v1/erp/receipts/{id}/fifo-suggestion", "erp.receipt", None),
    ("POST", "/api/v1/erp/payments/{id}/confirm", "erp.payment", None),
    (
        "POST",
        "/api/v1/erp/purchase-invoices/{id}/confirm",
        "erp.purchase_invoice",
        None,
    ),
    (
        "GET",
        "/api/v1/erp/journal-preview?kind=SALES&sourceId={id}",
        "erp.sales_record",
        None,
    ),
]
# 본문 안의 참조 id도 같은 공간으로 한정된다(대상을 못 찾으면 404).
BODY_CASES = [
    (
        "/api/v1/erp/shipments",
        "erp.shipment_order",
        "shipmentOrderId",
        {"shipmentNo": "ISO-SH"},
    ),
    (
        "/api/v1/erp/tax-invoices",
        "erp.sales_record",
        "salesRecordId",
        {},
    ),
]


def _headers(created) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": str(uuid4())}


def _first_id(engine, table: str, workspace_id: int) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text(f"SELECT min(id) FROM {table} WHERE workspace_id=:w"),
            {"w": workspace_id},
        ).scalar_one()


def _fingerprint(engine, workspace_id: int) -> dict[str, int]:
    """다른 공간의 업무 행 수와 멱등 영수증 수. 격리 요청 뒤에도 같아야 한다."""
    tables = {t for _, _, t, _ in CASES} | {"core.request_receipt"}
    with engine.connect() as connection:
        return {
            t: connection.execute(
                text(f"SELECT count(*) FROM {t} WHERE workspace_id=:w"),
                {"w": workspace_id},
            ).scalar_one()
            for t in sorted(tables)
        }


@pytest.fixture
def two_spaces(guest_space):
    """A(guest_space)와 별도 클라이언트의 게스트 B. B는 conftest 정리에서 함께 지워진다."""
    client, created, engine = guest_space
    with TestClient(create_app(), base_url="https://testserver") as other:
        response = other.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "테스트 게스트"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201, response.text
        with engine.begin() as connection:  # W0-1: B도 모든 솔루션을 연 상태
            for module in SCHEMAS:
                copy_module_seed(
                    connection, response.json()["data"]["workspaceId"], module
                )
        yield (
            client,
            created,
            other.get("/api/v1/core/sessions/current").json()["data"],
            engine,
        )


def test_other_space_ids_are_not_found_in_every_module(two_spaces):
    client, created, other, engine = two_spaces
    before = _fingerprint(engine, other["workspaceId"])
    leaked = []
    for method, path, table, body in CASES:
        foreign = _first_id(engine, table, other["workspaceId"])
        own = _first_id(engine, table, created["workspaceId"])
        assert foreign is not None and own is not None, table
        response = client.request(
            method, path.format(id=foreign), json=body, headers=_headers(created)
        )
        if response.status_code != 404:
            leaked.append((method, path, response.status_code))
        mine = client.request(
            method, path.format(id=own), json=body, headers=_headers(created)
        )
        assert mine.status_code != 404, (method, path, mine.text)
    assert leaked == []
    assert _fingerprint(engine, other["workspaceId"]) == before


def test_foreign_ids_inside_body_are_not_found(two_spaces):
    client, created, other, engine = two_spaces
    for path, table, field, body in BODY_CASES:
        foreign = _first_id(engine, table, other["workspaceId"])
        response = client.post(
            path, json={**body, field: foreign}, headers=_headers(created)
        )
        assert response.status_code == 404, (path, response.text)


def test_business_idempotency_same_body_replays_and_other_body_conflicts(guest_space):
    client, created, _ = guest_space
    headers = {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "fs021-plan"}
    body = {"planCode": "SP-FS021", "targetMonth": "2026-11"}
    first = client.post("/api/v1/erp/sales-plans", json=body, headers=headers)
    again = client.post("/api/v1/erp/sales-plans", json=body, headers=headers)
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    other = client.post(
        "/api/v1/erp/sales-plans",
        json={**body, "targetMonth": "2026-12"},
        headers=headers,
    )
    assert other.status_code == 422
    assert other.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_idempotency_key_older_than_24_hours_is_rejected(guest_space):
    client, created, engine = guest_space
    headers = {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "fs021-old"}
    body = {"planCode": "SP-FS021-OLD", "targetMonth": "2026-11"}
    assert (
        client.post("/api/v1/erp/sales-plans", json=body, headers=headers).status_code
        == 201
    )
    with engine.begin() as connection:  # 영수증을 25시간 전으로 돌린다
        connection.execute(
            text(
                "UPDATE core.request_receipt SET created_at = created_at - interval '25 hours' "
                "WHERE workspace_id=:w AND request_key='fs021-old'"
            ),
            {"w": created["workspaceId"]},
        )
    expired = client.post("/api/v1/erp/sales-plans", json=body, headers=headers)
    assert expired.status_code == 422
    assert expired.json()["error"]["message"] == "만료된 멱등 키입니다."
