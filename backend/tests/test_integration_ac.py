"""FS-021 AC 보강 — AC-35~80 추적표에서 테스트가 없던 항목. 테스트 이름에 AC 번호를 붙인다.

동시성은 스레드 두 개로 같은 순간에 보내고, 실패 주입은 monkeypatch로 트랜잭션 중간에 예외를 낸다.
대응표는 docs/agent/통합검증_FS-021.md.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import fs.common.auth
import fs.core.service
import fs.erp.revenue
import pytest
from fastapi.testclient import TestClient
from fs.main import create_app
from seed.copy import SCHEMAS, copy_module_seed
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

MES = "/api/v1/mes"
ERP = "/api/v1/erp"


def _headers(created, key=None) -> dict[str, str]:
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": key or str(uuid4()),
    }


def _count(engine, sql: str, **params) -> int:
    with engine.connect() as connection:
        return connection.execute(text(sql), params).scalar_one()


def _new_guest():
    """쿠키 없는 새 방문자의 게스트 생성 요청(세션이 있는 클라이언트는 다른 경로로 처리된다)."""
    with TestClient(create_app(), base_url="https://testserver") as fresh:
        return fresh.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "테스트 게스트"},
            headers={"Idempotency-Key": str(uuid4())},
        )


def _guests(engine) -> int:
    return _count(
        engine, "SELECT count(*) FROM core.workspace WHERE workspace_kind='GUEST'"
    )


def _running(client) -> tuple[dict, dict]:
    lot = next(x for x in client.get(f"{MES}/lots").json()["data"] if x["running"])
    execution = next(
        e
        for e in client.get(f"{MES}/executions").json()["data"]
        if e["lotId"] == lot["id"]
    )
    detail = client.get(f"{MES}/lots/{lot['id']}").json()["data"]
    return execution, {"goodQty": detail["steps"][0]["goodQty"], "defectQty": "0"}


# ---- 동시성 ----
def test_ac37_ac65_concurrent_results_with_other_keys_confirm_once(guest_space):
    client, created, engine = guest_space
    execution, body = _running(client)
    path = f"{MES}/executions/{execution['id']}/result"

    def post(key: str) -> int:
        return client.post(path, json=body, headers=_headers(created, key)).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(post, ["ac37-a", "ac37-b"])) == [200, 409]
    assert (
        _count(
            engine,
            "SELECT count(*) FROM mes.operation_result WHERE execution_id=:id",
            id=execution["id"],
        )
        == 1
    )
    # AC-65: 계정 없는 게스트의 요청 결과는 성공 키 1건, 주체는 GUEST(사용자 id 없음)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM core.request_receipt WHERE workspace_id=:w "
            "AND request_key IN ('ac37-a','ac37-b') AND actor_kind='GUEST' "
            "AND actor_user_id IS NULL",
            w=created["workspaceId"],
        )
        == 1
    )


def test_ac36_module_off_races_business_write(guest_space):
    client, created, engine = guest_space
    body = {"planCode": "SP-AC36", "targetMonth": "2026-11"}

    def switch_off() -> int:
        return client.patch(
            "/api/v1/core/workspace/modules/erp",
            json={"enabled": False},
            headers=_headers(created),
        ).status_code

    def write() -> tuple[int, str | None]:
        response = client.post(
            f"{ERP}/sales-plans", json=body, headers=_headers(created)
        )
        reason = (response.json().get("error") or {}).get("details", {}).get("reason")
        return response.status_code, reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = pool.submit(switch_off), pool.submit(write)  # 둘 다 먼저 보낸다
        off, (status, reason) = (f.result() for f in futures)
    assert off == 200
    assert status == 201 or (status == 409 and reason == "MODULE_DISABLED")
    # 모듈을 끈 뒤에는 어떤 쓰기도 통과하지 않는다
    again = client.post(
        f"{ERP}/sales-plans",
        json={**body, "planCode": "SP-AC36B"},
        headers=_headers(created),
    )
    assert again.json()["error"]["details"]["reason"] == "MODULE_DISABLED"
    made = _count(
        engine,
        "SELECT count(*) FROM erp.sales_plan WHERE workspace_id=:w AND plan_code LIKE 'SP-AC36%'",
        w=created["workspaceId"],
    )
    assert made == (1 if status == 201 else 0)


def test_ac35_reset_races_business_write(guest_space):
    client, created, engine = guest_space
    before = created["generationId"]

    def reset() -> int:
        return client.post(
            "/api/v1/core/workspace/generations", headers=_headers(created)
        ).status_code

    def write() -> int:
        return client.post(
            f"{ERP}/sales-plans",
            json={"planCode": "SP-AC35", "targetMonth": "2026-11"},
            headers=_headers(created),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = pool.submit(reset), pool.submit(write)
        reset_code, write_code = (f.result() for f in futures)
    assert reset_code == 201 and write_code == 201
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT generation_id FROM erp.sales_plan WHERE workspace_id=:w "
                    "AND plan_code='SP-AC35'"
                ),
                {"w": created["workspaceId"]},
            )
            .scalars()
            .all()
        )
        active = connection.execute(
            text("SELECT active_generation_id FROM core.workspace WHERE id=:w"),
            {"w": created["workspaceId"]},
        ).scalar_one()
    # 먼저 commit한 쪽만 유효: 쓰기가 먼저면 구세대에 1행(새 세대는 템플릿 복사본), 아니면 새 세대에 1행
    assert len(rows) == 1 and rows[0] in (before, active) and active != before


def test_ac60_concurrent_shipments_with_same_packing_no(guest_space):
    client, created, engine = guest_space
    orders = [
        o
        for o in client.get(f"{ERP}/shipment-orders").json()["data"]
        if o["shipOrderNo"] in ("SH-O-0005", "SH-O-0006")
    ]
    sales_before = _count(
        engine,
        "SELECT count(*) FROM erp.sales_record WHERE workspace_id=:w",
        w=created["workspaceId"],
    )

    def ship(order) -> int:
        body = {
            "shipmentNo": f"SH-AC60-{order['id']}",
            "shipmentOrderId": order["id"],
            "lines": [
                {"shipmentOrderLineId": order["lines"][0]["id"], "packingNo": "PL-AC60"}
            ],
        }
        return client.post(
            f"{ERP}/shipments", json=body, headers=_headers(created)
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(ship, orders)) == [201, 409]
    after = _count(
        engine,
        "SELECT count(*) FROM erp.sales_record WHERE workspace_id=:w",
        w=created["workspaceId"],
    )
    assert after == sales_before + 1


def test_ac66_concurrent_guest_creation_at_limit(guest_space, monkeypatch):
    _, _, engine = guest_space
    monkeypatch.setenv("GUEST_LIMIT", str(_guests(engine) + 1))

    def create(_) -> int:
        return _new_guest().status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, range(2))) == [201, 429]


# ---- 게스트 상한·회수 ----
def test_ac49_guest_limit_rejects_with_reason(guest_space, monkeypatch):
    _, _, engine = guest_space
    monkeypatch.setenv("GUEST_LIMIT", str(_guests(engine)))
    response = _new_guest()
    assert (response.status_code, response.json()["error"]["code"]) == (
        429,
        "RATE_LIMITED",
    )


def test_ac67_cleanup_keeps_unexpired_spaces(guest_space):
    _, _, engine = guest_space
    before = _guests(engine)
    with engine.begin() as connection:
        assert fs.core.service.cleanup_expired_guests(connection) == 0
    assert _guests(engine) == before


def test_ac70_expired_guest_cleanup_keeps_audit_snapshot(guest_space):
    client, created, engine = guest_space
    w = created["workspaceId"]
    # 감사 기록 하나를 만든다(소명 취소)
    receipt = next(
        r for r in client.get(f"{ERP}/receipts").json()["data"] if r["applications"]
    )
    apply_id = receipt["applications"][0]["id"]
    client.delete(
        f"{ERP}/receipts/{receipt['id']}/applications/{apply_id}",
        headers=_headers(created),
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace SET expires_at=now() - interval '1 hour' WHERE id=:w"
            ),
            {"w": w},
        )
        assert fs.core.service.cleanup_expired_guests(connection) == 1
    for table in (
        "core.workspace_module",
        "core.request_receipt",
        "core.data_generation",
    ):
        assert (
            _count(engine, f"SELECT count(*) FROM {table} WHERE workspace_id=:w", w=w)
            == 0
        )
    assert _count(engine, "SELECT count(*) FROM core.workspace WHERE id=:w", w=w) == 0
    assert (
        _count(
            engine,
            "SELECT count(*) FROM core.audit_event WHERE workspace_snapshot_id=:w "
            "AND scope_kind='RETIRED' AND action='erp.receipt_apply.delete'",
            w=w,
        )
        == 1
    )


def test_ac63_expiry_is_rechecked_after_workspace_lock(guest_space, monkeypatch):
    """인증(잠금 전)은 통과했지만 잠금 시점에 만료됐다면 쓰기는 410이고 아무것도 남지 않는다."""
    client, created, engine = guest_space
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace SET expires_at=now() - interval '1 second' WHERE id=:w"
            ),
            {"w": created["workspaceId"]},
        )

    class Before(datetime):  # 인증 단계만 과거 시각으로 본다
        @classmethod
        def now(cls, tz=None):
            return datetime(2000, 1, 1, tzinfo=UTC)

    monkeypatch.setattr(fs.common.auth, "datetime", Before)
    response = client.post(
        f"{ERP}/sales-plans",
        json={"planCode": "SP-AC63", "targetMonth": "2026-11"},
        headers=_headers(created),
    )
    assert (response.status_code, response.json()["error"]["code"]) == (
        410,
        "WORKSPACE_EXPIRED",
    )
    assert (
        _count(engine, "SELECT count(*) FROM erp.sales_plan WHERE plan_code='SP-AC63'")
        == 0
    )


def test_ac63_write_after_reclaim_fails(guest_space):
    client, created, engine = guest_space
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace SET expires_at=now() - interval '1 hour' WHERE id=:w"
            ),
            {"w": created["workspaceId"]},
        )
        fs.core.service.cleanup_expired_guests(connection)
    response = client.post(
        f"{ERP}/sales-plans",
        json={"planCode": "SP-AC63B", "targetMonth": "2026-11"},
        headers=_headers(created),
    )
    assert response.status_code in (401, 410)


# ---- 실패 주입 ----
def test_ac46_ac62_ac69_copy_failure_leaves_no_space(guest_space, monkeypatch):
    _, _, engine = guest_space
    original = fs.core.service.copy_template

    def copy_then_fail(*args, **kwargs):
        original(*args, **kwargs)  # 자기참조(패킹 단위)까지 복사한 뒤 실패
        raise RuntimeError("injected copy failure")

    monkeypatch.setattr(fs.core.service, "copy_template", copy_then_fail)
    guests = _guests(engine)
    generations = _count(engine, "SELECT count(*) FROM core.data_generation")
    lots = _count(engine, "SELECT count(*) FROM mes.packing_unit")
    with pytest.raises(RuntimeError, match="injected"):
        _new_guest()
    assert _guests(engine) == guests
    assert _count(engine, "SELECT count(*) FROM core.data_generation") == generations
    assert _count(engine, "SELECT count(*) FROM mes.packing_unit") == lots


def test_ac61_sale_failure_rolls_back_whole_shipment(guest_space, monkeypatch):
    client, created, engine = guest_space
    order = next(
        o
        for o in client.get(f"{ERP}/shipment-orders").json()["data"]
        if o["shipOrderNo"] == "SH-O-0005"
    )

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected revenue failure")

    monkeypatch.setattr(fs.erp.revenue, "recognize", fail)
    w = created["workspaceId"]
    counts = {
        t: _count(engine, f"SELECT count(*) FROM erp.{t} WHERE workspace_id=:w", w=w)
        for t in ("shipment", "shipment_line", "sales_record", "receivable")
    }
    with pytest.raises(RuntimeError, match="injected"):
        client.post(
            f"{ERP}/shipments",
            json={"shipmentNo": "SH-AC61", "shipmentOrderId": order["id"]},
            headers=_headers(created),
        )
    for table, n in counts.items():
        assert (
            _count(
                engine, f"SELECT count(*) FROM erp.{table} WHERE workspace_id=:w", w=w
            )
            == n
        )
    after = next(
        o
        for o in client.get(f"{ERP}/shipment-orders").json()["data"]
        if o["id"] == order["id"]
    )
    assert after["status"] == "open"


# ---- 도메인 규칙 ----
def test_ac56_work_order_is_stock_only(guest_space):
    _, created, engine = guest_space
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE mes.work_order SET order_type='ORDER' WHERE id=(SELECT min(id) "
                "FROM mes.work_order WHERE workspace_id=:w)"
            ),
            {"w": created["workspaceId"]},
        )


def test_ac76_split_instructions_ship_separately_then_close(guest_space):
    client, created, _ = guest_space
    order = next(
        o
        for o in client.get(f"{ERP}/sales-orders").json()["data"]
        if o["orderNo"] == "SO-0007"
    )
    first, second = order["lines"]

    def instruct(no: str, lines) -> dict:
        return client.post(
            f"{ERP}/shipment-orders",
            json={
                "shipOrderNo": no,
                "salesOrderId": order["id"],
                "orderedOn": "2026-09-24",
                "lines": [{"salesOrderLineId": i, "orderQty": q} for i, q in lines],
            },
            headers=_headers(created),
        ).json()["data"]

    a = instruct("SH-O-AC76A", [(first["id"], "1200")])
    b = instruct("SH-O-AC76B", [(first["id"], "800"), (second["id"], "2000")])
    status = []
    for ship_order in (a, b):
        client.post(
            f"{ERP}/shipments",
            json={
                "shipmentNo": f"SH-{ship_order['shipOrderNo']}",
                "shipmentOrderId": ship_order["id"],
            },
            headers=_headers(created),
        )
        status.append(
            next(
                o["status"]
                for o in client.get(f"{ERP}/sales-orders").json()["data"]
                if o["id"] == order["id"]
            )
        )
    assert status == ["shipping", "closed"]
    sales = [
        s
        for s in client.get(f"{ERP}/sales-records").json()["data"]
        if s["orderNo"] == "SO-0007"
    ]
    assert len(sales) == 2


def test_ac78_shipment_rejects_line_of_other_instruction(guest_space):
    client, created, _ = guest_space
    orders = {
        o["shipOrderNo"]: o for o in client.get(f"{ERP}/shipment-orders").json()["data"]
    }
    target, other = orders["SH-O-0005"], orders["SH-O-0007"]
    response = client.post(
        f"{ERP}/shipments",
        json={
            "shipmentNo": "SH-AC78",
            "shipmentOrderId": target["id"],
            "lines": [
                {"shipmentOrderLineId": other["lines"][0]["id"], "packingNo": None}
            ],
        },
        headers=_headers(created),
    )
    assert response.status_code == 400
    assert "lines" in response.json()["error"]["details"]["fields"]


# ---- 부분 → 검증 보강 (사용자 요청 2026-09-26) ----
def test_ac68_two_guest_copies_have_own_scope_and_full_rows(guest_space):
    _, created, engine = guest_space
    other = _new_guest().json()["data"]
    with (
        engine.begin() as connection
    ):  # W0-1: 두 번째 게스트도 모든 솔루션을 연 상태로 비교한다
        for module in SCHEMAS:
            copy_module_seed(connection, other["workspaceId"], module)
    with engine.connect() as connection:
        template = connection.execute(
            text(
                "SELECT id, active_generation_id FROM core.workspace "
                "WHERE workspace_kind='TEMPLATE'"
            )
        ).one()
        tables = (
            connection.execute(
                text(
                    "SELECT table_schema || '.' || table_name FROM information_schema.columns "
                    "WHERE table_schema IN ('mes','erp','fems') AND column_name='generation_id'"
                )
            )
            .scalars()
            .all()
        )
        for table in tables:
            counts = {}
            for w, g in (
                (template.id, template.active_generation_id),
                (created["workspaceId"], created["generationId"]),
                (other["workspaceId"], other["generationId"]),
            ):
                rows = connection.execute(
                    text(
                        f"SELECT count(*) total, count(*) FILTER (WHERE generation_id=:g) mine "
                        f"FROM {table} WHERE workspace_id=:w"
                    ),
                    {"w": w, "g": g},
                ).one()
                assert rows.total == rows.mine, (
                    table
                )  # 모든 행이 자기 S(공간·활성 세대)
                counts[w] = rows.total
            assert len(set(counts.values())) == 1, (table, counts)  # 원본과 같은 행 수
    assert (
        created["generationId"]
        != other["generationId"]
        != template.active_generation_id
    )


def test_ac73_rejected_order_leaves_every_plan_allocation(guest_space):
    client, created, _ = guest_space

    def allocations():
        return {
            line["id"]: line["allocatedQty"]
            for plan in client.get(f"{MES}/production-plans").json()["data"]
            for line in plan["lines"]
        }

    items = {i["itemCode"]: i["id"] for i in client.get(f"{MES}/items").json()["data"]}
    line = next(
        line
        for plan in client.get(f"{MES}/production-plans").json()["data"]
        if plan["status"] == "confirmed"
        for line in plan["lines"]
        if line["itemId"] == items["FG-C100"] and float(line["remainingQty"]) > 0
    )
    foreign_route = next(
        r["id"]
        for r in client.get(f"{MES}/routes").json()["data"]
        if r["routeCode"] == "RT-C200" and r["status"] == "published"
    )
    before = allocations()
    response = client.post(
        f"{MES}/work-orders",
        json={
            "productionPlanLineId": line["id"],
            "routeVersionId": foreign_route,
            "planQty": "10",
            "planStartDate": "2026-09-28",
            "planEndDate": "2026-09-30",
        },
        headers=_headers(created),
    )
    assert response.status_code == 400
    assert allocations() == before


def test_ac74_unfinished_lot_cannot_be_packed(guest_space):
    client, created, _ = guest_space
    lot = next(
        x
        for x in client.get(f"{MES}/lots").json()["data"]
        if x["status"] == "in_progress"
    )
    box = client.post(
        f"{MES}/packing-units", json={"packingKind": "BOX"}, headers=_headers(created)
    ).json()["data"]
    response = client.put(
        f"{MES}/packing-units/{box['id']}/members",
        json={"lotId": lot["id"], "packedQty": "1"},
        headers=_headers(created),
    )
    assert response.status_code == 400
    assert "lotId" in response.json()["error"]["details"]["fields"]


def test_ac75_received_pallet_structure_is_unchanged_after_rejections(guest_space):
    client, created, _ = guest_space

    def pallet():
        return next(
            u
            for u in client.get(f"{MES}/packing-units").json()["data"]
            if u["packingNo"] == "PL-0002"
        )

    before = pallet()
    assert before["status"] == "received"
    child = before["childIds"][0]
    detach = client.put(
        f"{MES}/packing-units/{child}/parent",
        json={"parentPackingUnitId": None},
        headers=_headers(created),
    )
    single = client.post(
        f"{MES}/finished-goods-receipts",
        json={"packingUnitId": child},
        headers=_headers(created),
    )
    assert detach.status_code == 409 and single.status_code == 409
    after = pallet()
    assert (after["childIds"], after["totalQty"], after["status"]) == (
        before["childIds"],
        before["totalQty"],
        "received",
    )
