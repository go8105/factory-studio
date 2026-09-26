"""FS-019b E-03 판매계획 API. 검증 항목마다 테스트를 나눈다."""

from uuid import uuid4

import pytest

BASE = "/api/v1/erp"


@pytest.fixture
def erp(guest_space):
    return guest_space[:2]


def _call(client, created, method: str, path: str, body=None):
    return client.request(
        method,
        f"{BASE}{path}",
        json=body,
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": str(uuid4())},
    )


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _item(client, code: str) -> int:
    rows = client.get(f"{BASE}/items?limit=200").json()["data"]
    return next(r["id"] for r in rows if r["itemCode"] == code)


def _new_plan(client, created, code="SP-T01") -> dict:
    response = _call(
        client,
        created,
        "POST",
        "/sales-plans",
        {"planCode": code, "targetMonth": "2026-10"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_seed_plans_are_confirmed_with_lines(erp):
    client, _ = erp
    plans = client.get(f"{BASE}/sales-plans").json()["data"]
    assert [(p["planCode"], p["status"], len(p["lines"])) for p in plans] == [
        ("SP-2026-09", "confirmed", 3),
        ("SP-2026-08", "confirmed", 3),
    ]


def test_confirmed_plan_is_immutable(erp):
    client, created = erp
    plan = client.get(f"{BASE}/sales-plans").json()["data"][0]
    for method, path, body in [
        ("PATCH", f"/sales-plans/{plan['id']}", {"targetMonth": "2026-11"}),
        ("PUT", f"/sales-plans/{plan['id']}/lines", {"lines": []}),
        ("POST", f"/sales-plans/{plan['id']}/confirm", None),
        ("DELETE", f"/sales-plans/{plan['id']}", None),
    ]:
        response = _call(client, created, method, path, body)
        assert response.status_code == 409 and _reason(response) == "PLAN_CONFIRMED"


def test_lines_take_item_unit_and_confirm_sets_time(erp):
    client, created = erp
    plan = _new_plan(client, created)
    item = _item(client, "FG-C100")
    lines = _call(
        client,
        created,
        "PUT",
        f"/sales-plans/{plan['id']}/lines",
        {"lines": [{"itemId": item, "planQty": "1200"}]},
    ).json()["data"]["lines"]
    assert [(x["planQty"], x["unit"]) for x in lines] == [("1200.000", "EA")]
    confirmed = _call(client, created, "POST", f"/sales-plans/{plan['id']}/confirm")
    data = confirmed.json()["data"]
    assert data["status"] == "confirmed" and data["confirmedAt"]


def test_duplicate_item_rejected(erp):
    client, created = erp
    plan = _new_plan(client, created)
    item = _item(client, "FG-C100")
    response = _call(
        client,
        created,
        "PUT",
        f"/sales-plans/{plan['id']}/lines",
        {"lines": [{"itemId": item, "planQty": "1"}, {"itemId": item, "planQty": "2"}]},
    )
    assert response.status_code == 400
    assert "같은 품목" in response.json()["error"]["details"]["fields"]["lines"]


def test_empty_plan_cannot_confirm(erp):
    client, created = erp
    plan = _new_plan(client, created)
    response = _call(client, created, "POST", f"/sales-plans/{plan['id']}/confirm")
    assert response.status_code == 409 and _reason(response) == "EMPTY_PLAN"


def test_duplicate_code_and_draft_delete(erp):
    client, created = erp
    dup = _call(
        client,
        created,
        "POST",
        "/sales-plans",
        {"planCode": "SP-2026-09", "targetMonth": "2026-10"},
    )
    assert dup.json()["error"]["details"]["fields"] == {
        "planCode": "이미 사용 중인 코드입니다."
    }
    plan = _new_plan(client, created)
    _call(
        client,
        created,
        "PUT",
        f"/sales-plans/{plan['id']}/lines",
        {"lines": [{"itemId": _item(client, "FG-C100"), "planQty": "5"}]},
    )
    assert (
        _call(client, created, "DELETE", f"/sales-plans/{plan['id']}").status_code
        == 204
    )
    codes = [p["planCode"] for p in client.get(f"{BASE}/sales-plans").json()["data"]]
    assert "SP-T01" not in codes
