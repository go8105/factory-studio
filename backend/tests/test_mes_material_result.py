"""FS-020e MES 자재 투입(M-06)·실적(M-07) API. 검증 항목마다 테스트를 나눈다."""

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


def _call(client, created, method: str, path: str, key: str, body=None):
    return client.request(
        method, f"{BASE}{path}", json=body, headers=_headers(created, key)
    )


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _item(client, code: str) -> dict:
    return next(i for i in _rows(client, "/items") if i["itemCode"] == code)


def _running(client) -> dict:
    """시드의 실행 중 조립 공정(W11·W12). 시드는 사출 수지·조립 핀 투입을 이미 기록해 두었다."""
    return _rows(client, "/executions")[0]


def _fresh(client, created) -> dict:
    """대기 LOT의 첫 공정(사출)을 새로 시작한 실행. 아직 투입 기록이 없다."""
    lot = next(x for x in _rows(client, "/lots") if x["status"] == "ready")
    equipment = next(
        e for e in _rows(client, "/equipments") if e["equipmentCode"] == "INJ-01"
    )
    response = _call(
        client,
        created,
        "POST",
        f"/lots/{lot['id']}/executions",
        "fresh",
        {"routeStepId": lot["nextStep"]["routeStepId"], "equipmentId": equipment["id"]},
    )
    assert response.status_code == 201, response.text
    return next(e for e in _rows(client, "/executions") if e["lotId"] == lot["id"])


def _issue(client, created, execution_id: int, key: str, **body):
    return _call(
        client,
        created,
        "POST",
        f"/executions/{execution_id}/material-issues",
        key,
        body,
    )


def test_requirement_subtracts_what_the_lot_already_used(mes):
    client, created = mes
    fresh = _fresh(client, created)
    lines = {
        line["materialItemId"]: line
        for line in _rows(client, f"/executions/{fresh['id']}/bom-requirement")
    }
    pbt = lines[_item(client, "RM-PBT")["id"]]
    pin = lines[_item(client, "RM-PIN")["id"]]
    # 새 LOT: 아직 투입이 없어 제안량 = 기준 소요량. 핀(EA)은 올림 정수.
    assert (pbt["unit"], Decimal(pbt["issuedQty"])) == ("KG", 0)
    assert pbt["suggestedQty"] == pbt["requiredQty"]
    assert (
        Decimal(pin["requiredQty"]) == Decimal(pin["requiredQty"]).to_integral_value()
    )
    # 수지를 일부 투입하면 같은 LOT의 제안량이 그만큼 줄어든다.
    _issue(
        client,
        created,
        fresh["id"],
        "part",
        materialItemId=pbt["materialItemId"],
        issuedQty="10",
        unit="KG",
    )
    after = {
        line["materialItemId"]: line
        for line in _rows(client, f"/executions/{fresh['id']}/bom-requirement")
    }[pbt["materialItemId"]]
    assert Decimal(after["suggestedQty"]) == Decimal(pbt["requiredQty"]) - 10


def test_seed_running_step_needs_nothing_more(mes):
    client, _ = mes
    lines = _rows(client, f"/executions/{_running(client)['id']}/bom-requirement")
    assert all(Decimal(line["suggestedQty"]) == 0 for line in lines)


def test_order_without_bom_has_empty_requirement(mes):
    client, created = mes
    orders = _rows(client, "/work-orders")
    no_bom = next(
        o for o in orders if o["bomVersionId"] is None and o["status"] == "released"
    )
    _call(client, created, "POST", f"/work-orders/{no_bom['id']}/lot", "lot")
    lot = next(x for x in _rows(client, "/lots") if x["orderNo"] == no_bom["orderNo"])
    equipment = next(
        e for e in _rows(client, "/equipments") if e["equipmentCode"] == "INJ-01"
    )
    _call(
        client,
        created,
        "POST",
        f"/lots/{lot['id']}/executions",
        "start",
        {"routeStepId": lot["nextStep"]["routeStepId"], "equipmentId": equipment["id"]},
    )
    execution = next(e for e in _rows(client, "/executions") if e["lotId"] == lot["id"])
    response = client.get(f"{BASE}/executions/{execution['id']}/bom-requirement")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_issue_is_recorded_with_bom_reference(mes):
    client, created = mes
    execution = _fresh(client, created)
    pin = _item(client, "RM-PIN")
    response = _issue(
        client,
        created,
        execution["id"],
        "pin",
        materialItemId=pin["id"],
        issuedQty="8000",
        unit="EA",
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert (data["issuedQty"], data["unit"], data["materialLotId"]) == (
        "8000.000",
        "EA",
        None,
    )
    assert data["bomVersionId"] is not None
    assert len(_rows(client, f"/executions/{execution['id']}/material-issues")) == 1


def test_material_outside_bom_has_no_bom_reference(mes):
    client, created = mes
    execution = _running(client)
    other = _item(client, "SF-H100")
    response = _issue(
        client,
        created,
        execution["id"],
        "other",
        materialItemId=other["id"],
        issuedQty="5",
        unit="EA",
    )
    assert response.json()["data"]["bomVersionId"] is None


def test_duplicate_issue_without_lot_is_rejected(mes):
    client, created = mes
    execution = _fresh(client, created)
    pin = _item(client, "RM-PIN")
    body = {"materialItemId": pin["id"], "issuedQty": "100", "unit": "EA"}
    _issue(client, created, execution["id"], "first", **body)
    response = _issue(client, created, execution["id"], "second", **body)
    assert response.status_code == 409
    assert _reason(response) == "DUPLICATE_ISSUE"


def test_issue_unit_may_be_conversion_unit(mes):
    client, created = mes
    execution = _fresh(client, created)
    pin = _item(client, "RM-PIN")
    ok = _issue(
        client,
        created,
        execution["id"],
        "box",
        materialItemId=pin["id"],
        issuedQty="1",
        unit="BOX",
    )
    assert ok.status_code == 201
    bad = _issue(
        client,
        created,
        execution["id"],
        "kg",
        materialItemId=_item(client, "RM-PBT")["id"],
        issuedQty="1",
        unit="EA",
    )
    assert bad.status_code == 400
    assert "unit" in bad.json()["error"]["details"]["fields"]


def test_zero_quantity_is_rejected(mes):
    client, created = mes
    execution = _running(client)
    response = _issue(
        client,
        created,
        execution["id"],
        "zero",
        materialItemId=_item(client, "RM-PIN")["id"],
        issuedQty="0",
        unit="EA",
    )
    assert response.status_code == 400


def test_material_lot_must_be_same_item(mes):
    client, created = mes
    execution = _running(client)
    finished = next(x for x in _rows(client, "/lots") if x["status"] == "completed")
    response = _issue(
        client,
        created,
        execution["id"],
        "lot",
        materialItemId=_item(client, "RM-PIN")["id"],
        materialLotId=finished["id"],
        issuedQty="1",
        unit="EA",
    )
    assert response.status_code == 400
    assert "materialLotId" in response.json()["error"]["details"]["fields"]


def test_confirmed_execution_rejects_issue(mes):
    client, created = mes
    detail = client.get(
        f"{BASE}/lots/{next(x for x in _rows(client, '/lots') if x['status'] == 'completed')['id']}"
    ).json()["data"]
    execution_id = detail["steps"][0]["executionId"]
    response = _issue(
        client,
        created,
        execution_id,
        "late",
        materialItemId=_item(client, "RM-PIN")["id"],
        issuedQty="1",
        unit="EA",
    )
    assert response.status_code == 409
    assert _reason(response) == "RESULT_CONFIRMED"


def test_issue_can_be_removed_only_while_running(mes):
    client, created = mes
    execution = _fresh(client, created)
    pin = _item(client, "RM-PIN")
    issue = _issue(
        client,
        created,
        execution["id"],
        "rm",
        materialItemId=pin["id"],
        issuedQty="10",
        unit="EA",
    ).json()["data"]
    removed = _call(
        client,
        created,
        "DELETE",
        f"/executions/{execution['id']}/material-issues/{issue['id']}",
        "del",
    )
    assert removed.status_code == 204
    again = _issue(
        client,
        created,
        execution["id"],
        "rm2",
        materialItemId=pin["id"],
        issuedQty="10",
        unit="EA",
    ).json()["data"]
    lot = next(x for x in _rows(client, "/lots") if x["id"] == execution["lotId"])
    _call(
        client,
        created,
        "POST",
        f"/executions/{execution['id']}/result",
        "confirm",
        {"goodQty": lot["running"]["inputQty"], "defectQty": "0"},
    )
    locked = _call(
        client,
        created,
        "DELETE",
        f"/executions/{execution['id']}/material-issues/{again['id']}",
        "del2",
    )
    assert _reason(locked) == "RESULT_CONFIRMED"


def test_results_list_shows_all_defective_reason(mes):
    client, _ = mes
    results = _rows(client, "/results")
    defective = [
        r
        for r in results
        if r["completionReason"] == "all_defective" and r["goodQty"] == "0.000"
    ]
    assert len(defective) == 1
    assert defective[0]["defectQty"] == defective[0]["inputQty"]
    assert defective[0]["defectReason"]
    assert all(
        Decimal(r["goodQty"]) + Decimal(r["defectQty"]) == Decimal(r["inputQty"])
        for r in results
    )
