"""FS-020d MES LOT 현황(M-04)·공정 실행(M-05) API. 검증 항목마다 테스트를 나눈다."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

BASE = "/api/v1/mes"


@pytest.fixture
def mes(guest_space):
    return guest_space[:2]


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _rows(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _post(client, created, path: str, key: str, body=None):
    return client.post(f"{BASE}{path}", json=body, headers=_headers(created, key))


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _lots(client) -> list[dict]:
    return _rows(client, "/lots")


def _lot_of_order(client, order_no: str) -> dict:
    return next(lot for lot in _lots(client) if lot["orderNo"] == order_no)


def _equipment(client, code: str) -> int:
    return next(
        e["id"] for e in _rows(client, "/equipments") if e["equipmentCode"] == code
    )


def _process_code(client, process_id: int) -> str:
    return next(
        p["processCode"] for p in _rows(client, "/processes") if p["id"] == process_id
    )


def _lot_with_next(client, process: str, status: str = "in_progress") -> dict:
    """다음 공정이 process인 LOT (시드: R01·R02는 첫 공정, W07·W08은 조립, W09·W10은 검사)."""
    for lot in _lots(client):
        step = lot["nextStep"]
        if (
            lot["status"] == status
            and step
            and _process_code(client, step["processId"]) == process
        ):
            return lot
    raise AssertionError(process)


def _start(client, created, lot: dict, equipment: str, key: str):
    return _post(
        client,
        created,
        f"/lots/{lot['id']}/executions",
        key,
        {
            "routeStepId": lot["nextStep"]["routeStepId"],
            "equipmentId": _equipment(client, equipment),
        },
    )


def _running_of(client, lot_id: int) -> dict:
    return next(e for e in _rows(client, "/executions") if e["lotId"] == lot_id)


# ---- M-04 LOT 현황 ----
def test_lot_list_summarises_progress(mes):
    client, _ = mes
    lots = _lots(client)
    assert len(lots) == 26
    defective = next(lot for lot in lots if lot["completionReason"] == "all_defective")
    assert (defective["status"], defective["finalGoodQty"]) == ("completed", "0.000")
    ready = [lot for lot in lots if lot["status"] == "ready"]
    assert len(ready) == 2
    assert ready[0]["nextStep"]["sequenceNo"] == 1
    assert ready[0]["nextStep"]["inputQty"] == ready[0]["planQty"]
    running = [lot for lot in lots if lot["running"]]
    assert len(running) == 2
    assert all(lot["running"]["inputQty"] for lot in running)


def test_lot_detail_is_one_traceability_response(mes):
    client, _ = mes
    lot = next(
        x
        for x in _lots(client)
        if x["status"] == "completed" and x["completionReason"] == "normal"
    )
    detail = client.get(f"{BASE}/lots/{lot['id']}").json()["data"]
    assert [s["sequenceNo"] for s in detail["steps"]] == [1, 2, 3]
    assert all(s["executionStatus"] == "completed" for s in detail["steps"])
    # 앞 단계 양품이 다음 단계 투입이다.
    for before, after in zip(detail["steps"], detail["steps"][1:], strict=False):
        assert after["inputQty"] == before["goodQty"]
    assert [len(s["materialIssues"]) for s in detail["steps"]] == [1, 1, 0]


# ---- M-05 공정 시작 (TX-01) ----
def test_first_start_moves_order_and_lot_in_progress(mes):
    client, created = mes
    lot = _lot_with_next(client, "INJ", status="ready")
    response = _start(client, created, lot, "INJ-01", "start")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert (data["status"], data["orderStatus"]) == ("in_progress", "in_progress")
    assert data["steps"][0]["executionStatus"] == "running"
    order = next(
        o for o in _rows(client, "/work-orders") if o["orderNo"] == lot["orderNo"]
    )
    assert order["startedAt"] is not None


def test_start_must_follow_route_order(mes):
    client, created = mes
    lot = _lot_with_next(client, "INJ", status="ready")
    detail = client.get(f"{BASE}/lots/{lot['id']}").json()["data"]
    response = _post(
        client,
        created,
        f"/lots/{lot['id']}/executions",
        "order",
        {
            "routeStepId": detail["steps"][1]["routeStepId"],
            "equipmentId": _equipment(client, "ASM-02"),
        },
    )
    assert response.status_code == 409
    assert _reason(response) == "OUT_OF_ORDER"


def test_equipment_must_be_allowed_for_process(mes):
    client, created = mes
    lot = _lot_with_next(client, "INJ", status="ready")
    response = _start(client, created, lot, "ASM-02", "not-allowed")
    assert response.status_code == 400
    assert "equipmentId" in response.json()["error"]["details"]["fields"]


def test_inactive_equipment_is_rejected(mes):
    client, created = mes
    client.patch(
        f"{BASE}/equipments/{_equipment(client, 'INJ-02')}",
        json={"isActive": False},
        headers=_headers(created, "off"),
    )
    lot = _lot_with_next(client, "INJ", status="ready")
    response = _start(client, created, lot, "INJ-02", "inactive")
    assert response.status_code == 400


def test_busy_equipment_is_rejected(mes):
    client, created = mes
    busy = _rows(client, "/executions")[0]
    code = next(
        e["equipmentCode"]
        for e in _rows(client, "/equipments")
        if e["id"] == busy["equipmentId"]
    )
    lot = _lot_with_next(client, "ASM")
    response = _start(client, created, lot, code, "busy")
    assert response.status_code == 409
    assert _reason(response) == "EQUIPMENT_BUSY"
    assert response.json()["error"]["details"]["lotNo"] == busy["lotNo"]


def test_concurrent_starts_on_one_equipment(mes):
    client, created = mes
    ready = [lot for lot in _lots(client) if lot["status"] == "ready"]
    assert len(ready) == 2

    def start(pair):
        lot, key = pair
        return _start(client, created, lot, "INJ-03", key).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(start, zip(ready, ["race-a", "race-b"], strict=True)))
    assert codes == [201, 409]


def test_running_step_blocks_next_start(mes):
    client, created = mes
    lot = next(x for x in _lots(client) if x["running"])
    response = _post(
        client,
        created,
        f"/lots/{lot['id']}/executions",
        "running",
        {
            "routeStepId": lot["running"]["routeStepId"],
            "equipmentId": _equipment(client, "INS-01"),
        },
    )
    assert response.status_code == 409
    assert _reason(response) == "STEP_RUNNING"


def test_completed_lot_cannot_start(mes):
    client, created = mes
    lot = next(x for x in _lots(client) if x["status"] == "completed")
    detail = client.get(f"{BASE}/lots/{lot['id']}").json()["data"]
    response = _post(
        client,
        created,
        f"/lots/{lot['id']}/executions",
        "done",
        {
            "routeStepId": detail["steps"][0]["routeStepId"],
            "equipmentId": _equipment(client, "INJ-01"),
        },
    )
    assert _reason(response) == "LOT_NOT_STARTABLE"


# ---- 공정 완료 = 실적 확정 (TX-02) ----
def _confirm(client, created, execution_id: int, key: str, **body):
    return _post(client, created, f"/executions/{execution_id}/result", key, body)


def test_result_must_balance_server_input(mes):
    client, created = mes
    lot = next(x for x in _lots(client) if x["running"])
    execution = _running_of(client, lot["id"])
    detail = client.get(f"{BASE}/lots/{lot['id']}").json()["data"]
    input_qty = Decimal(detail["steps"][0]["goodQty"])
    wrong = _confirm(
        client,
        created,
        execution["id"],
        "wrong",
        goodQty=str(input_qty - 1),
        defectQty="0",
    )
    assert wrong.status_code == 400
    assert "goodQty" in wrong.json()["error"]["details"]["fields"]
    no_reason = _confirm(
        client,
        created,
        execution["id"],
        "reason",
        goodQty=str(input_qty - 5),
        defectQty="5",
    )
    assert "defectReason" in no_reason.json()["error"]["details"]["fields"]


def test_middle_result_opens_next_step(mes):
    client, created = mes
    lot = next(x for x in _lots(client) if x["running"])
    execution = _running_of(client, lot["id"])
    detail = client.get(f"{BASE}/lots/{lot['id']}").json()["data"]
    input_qty = Decimal(detail["steps"][0]["goodQty"])
    response = _confirm(
        client,
        created,
        execution["id"],
        "ok",
        goodQty=str(input_qty - 10),
        defectQty="10",
        defectReason="버 발생",
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "in_progress"
    assert data["steps"][1]["executionStatus"] == "completed"
    assert Decimal(data["nextStep"]["inputQty"]) == input_qty - 10


def test_zero_good_ends_lot_as_all_defective(mes):
    client, created = mes
    lot = next(x for x in _lots(client) if x["running"])
    execution = _running_of(client, lot["id"])
    detail = client.get(f"{BASE}/lots/{lot['id']}").json()["data"]
    input_qty = detail["steps"][0]["goodQty"]
    response = _confirm(
        client,
        created,
        execution["id"],
        "zero",
        goodQty="0",
        defectQty=input_qty,
        defectReason="금형 손상",
    )
    data = response.json()["data"]
    assert (data["status"], data["completionReason"], data["orderStatus"]) == (
        "completed",
        "all_defective",
        "completed",
    )
    assert data["nextStep"] is None


def test_last_step_completes_lot_and_order(mes):
    client, created = mes
    lot = _lot_with_next(client, "INS")
    assert _start(client, created, lot, "INS-02", "ins").status_code == 201
    execution = _running_of(client, lot["id"])
    input_qty = lot["nextStep"]["inputQty"]
    response = _confirm(
        client, created, execution["id"], "last", goodQty=input_qty, defectQty="0"
    )
    data = response.json()["data"]
    assert (data["status"], data["completionReason"], data["orderStatus"]) == (
        "completed",
        "normal",
        "completed",
    )
    assert data["finalGoodQty"] == input_qty


def test_result_is_confirmed_once(mes):
    client, created = mes
    lot = next(x for x in _lots(client) if x["running"])
    execution = _running_of(client, lot["id"])
    detail = client.get(f"{BASE}/lots/{lot['id']}").json()["data"]
    body = {"goodQty": detail["steps"][0]["goodQty"], "defectQty": "0"}
    first = _confirm(client, created, execution["id"], "once", **body)
    replay = _confirm(client, created, execution["id"], "once", **body)
    assert first.json() == replay.json()
    other = _confirm(client, created, execution["id"], "twice", **body)
    assert _reason(other) == "ALREADY_COMPLETED"


def test_start_requires_csrf(mes):
    client, _ = mes
    lot = _lots(client)[0]
    response = client.post(
        f"{BASE}/lots/{lot['id']}/executions", json={}, headers={"Idempotency-Key": "k"}
    )
    assert response.status_code in (400, 403)
