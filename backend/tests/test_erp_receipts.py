"""FS-019e E-09 매출채권 현황 · E-10 수금·소명. 검증 항목마다 테스트를 나눈다."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text

BASE = "/api/v1/erp"


@pytest.fixture
def erp(guest_space):
    return guest_space[:2]


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        f"{BASE}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or str(uuid4()),
        },
    )


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _get(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _rv(client, shipment_no: str) -> dict:
    return next(
        r for r in _get(client, "/receivables") if r["shipmentNo"] == shipment_no
    )


def _partner(client, code: str) -> int:
    return next(p["id"] for p in _get(client, "/partners") if p["partnerCode"] == code)


def _receipt(client, created, amount: str, partner="C-001", no=None, confirm=True):
    body = {
        "receiptNo": no or f"RC-{uuid4().hex[:8]}",
        "partnerId": _partner(client, partner),
        "receivedOn": "2026-09-24",
        "amount": amount,
    }
    receipt = _call(client, created, "POST", "/receipts", body).json()["data"]
    if confirm:
        receipt = _call(
            client, created, "POST", f"/receipts/{receipt['id']}/confirm"
        ).json()["data"]
    return receipt


def _apply(client, created, receipt_id: int, lines: list[tuple[int, str]], key=None):
    body = {"lines": [{"receivableId": r, "amount": a} for r, a in lines]}
    return _call(
        client, created, "POST", f"/receipts/{receipt_id}/applications", body, key
    )


def test_seed_balances_and_derived_status(erp):
    client, _ = erp
    rows = {
        r["shipmentNo"]: (r["balance"], r["status"])
        for r in _get(client, "/receivables")
    }
    assert rows == {
        "SH-0001": ("1827800.00", "PARTIAL"),
        "SH-0002": ("5071440.00", "OPEN"),
        "SH-0003": ("0.00", "CLOSED"),
        "SH-0004": ("4786916.00", "PARTIAL"),
    }
    assert [a["receiptNo"] for a in _rv(client, "SH-0001")["applications"]] == [
        "RC-0001"
    ]


def test_filters_by_partner_and_status(erp):
    client, _ = erp
    closed = _get(client, "/receivables?status=CLOSED")
    assert [r["shipmentNo"] for r in closed] == ["SH-0003"]
    mine = _get(client, f"/receivables?partnerId={_partner(client, 'C-001')}")
    assert [r["shipmentNo"] for r in mine] == ["SH-0001", "SH-0004"]


def test_draft_receipt_cannot_apply_until_confirmed(erp):
    client, created = erp
    draft = next(r for r in _get(client, "/receipts") if r["receiptNo"] == "RC-0003")
    rv = _rv(client, "SH-0001")
    assert _reason(_apply(client, created, draft["id"], [(rv["id"], "1827800")])) == (
        "RECEIPT_NOT_CONFIRMED"
    )
    _call(client, created, "POST", f"/receipts/{draft['id']}/confirm")
    done = _apply(client, created, draft["id"], [(rv["id"], "1827800")])
    assert done.status_code == 201, done.text
    assert done.json()["data"]["unappliedAmount"] == "0.00"
    assert _rv(client, "SH-0001")["status"] == "CLOSED"


def test_receivable_limit_rolls_back_and_names_receivable(erp):
    client, created = erp
    receipt = _receipt(client, created, "10000000")
    first, second = _rv(client, "SH-0004"), _rv(client, "SH-0001")
    response = _apply(
        client,
        created,
        receipt["id"],
        [(first["id"], "100"), (second["id"], "2000000")],
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert (details["limit"], details["shipmentNo"], details["availableAmount"]) == (
        "RECEIVABLE",
        "SH-0001",
        "1827800.00",
    )
    assert _rv(client, "SH-0004")["balance"] == first["balance"]  # 첫 줄도 롤백


def test_receipt_limit_allows_overpayment_but_not_overapply(erp):
    client, created = erp
    receipt = _receipt(client, created, "100")
    rv = _rv(client, "SH-0001")
    over = _apply(client, created, receipt["id"], [(rv["id"], "200")])
    assert over.json()["error"]["details"]["limit"] == "RECEIPT"
    partial = _apply(client, created, receipt["id"], [(rv["id"], "40")]).json()["data"]
    assert (partial["appliedAmount"], partial["unappliedAmount"]) == ("40.00", "60.00")


def test_other_partner_receivable_rejected(erp):
    client, created = erp
    receipt = _receipt(client, created, "1000")
    response = _apply(
        client, created, receipt["id"], [(_rv(client, "SH-0002")["id"], "1")]
    )
    assert response.status_code == 400


def test_concurrent_applications_cannot_exceed_receivable(erp):
    client, created = erp
    rv = _rv(client, "SH-0001")  # 잔액 1,827,800
    receipts = [_receipt(client, created, "1000000") for _ in range(2)]

    def post(receipt) -> int:
        return _apply(
            client, created, receipt["id"], [(rv["id"], "1000000")]
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(post, receipts)) == [201, 409]
    assert _rv(client, "SH-0001")["balance"] == "827800.00"


def test_sale_cancel_and_application_race_one_wins(erp):
    client, created = erp
    sale = next(
        s for s in _get(client, "/sales-records") if s["shipmentNo"] == "SH-0002"
    )
    rv = _rv(client, "SH-0002")
    receipt = _receipt(client, created, "1000", partner="C-003")

    def cancel() -> int:
        return _call(
            client,
            created,
            "POST",
            f"/sales-records/{sale['id']}/cancel",
            {"reason": "경합"},
        ).status_code

    def apply() -> int:
        return _apply(client, created, receipt["id"], [(rv["id"], "1000")]).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = [f.result() for f in [pool.submit(cancel), pool.submit(apply)]]
    assert sorted(codes) in ([200, 409], [201, 409])  # 둘 다 성공하지 않는다


def test_cancelled_sale_receivable_is_excluded(erp):
    client, created = erp
    sale = next(
        s for s in _get(client, "/sales-records") if s["shipmentNo"] == "SH-0002"
    )
    rv_id = _rv(client, "SH-0002")["id"]
    _call(
        client,
        created,
        "POST",
        f"/sales-records/{sale['id']}/cancel",
        {"reason": "반품"},
    )
    assert all(r["shipmentNo"] != "SH-0002" for r in _get(client, "/receivables"))
    receipt = _receipt(client, created, "1000", partner="C-003")
    assert (
        _reason(_apply(client, created, receipt["id"], [(rv_id, "1")]))
        == "SALES_CANCELLED"
    )


def test_delete_application_is_physical_and_audited(guest_space):
    client, created, engine = guest_space
    receipt = _receipt(client, created, "500")
    rv = _rv(client, "SH-0001")
    data = _apply(client, created, receipt["id"], [(rv["id"], "500")]).json()["data"]
    apply_id = data["applications"][0]["id"]
    response = _call(
        client, created, "DELETE", f"/receipts/{receipt['id']}/applications/{apply_id}"
    )
    assert response.json()["data"]["unappliedAmount"] == "500.00"
    assert _rv(client, "SH-0001")["balance"] == rv["balance"]
    with engine.connect() as connection:
        left = connection.execute(
            text("SELECT count(*) FROM erp.receipt_apply WHERE id=:id"),
            {"id": apply_id},
        ).scalar_one()
        audit = connection.execute(
            text(
                "SELECT summary FROM core.audit_event WHERE action='erp.receipt_apply.delete' "
                "AND entity_key=:key"
            ),
            {"key": str(apply_id)},
        ).scalar_one()
    assert left == 0
    assert (audit["amount"], audit["receivableId"]) == ("500.00", rv["id"])


def test_fifo_suggests_oldest_first_without_saving(erp):
    client, created = erp
    receipt = _receipt(client, created, "3000000")
    suggestion = _get(client, f"/receipts/{receipt['id']}/fifo-suggestion")
    assert suggestion == [
        {"receivableId": _rv(client, "SH-0001")["id"], "amount": "1827800.00"},
        {"receivableId": _rv(client, "SH-0004")["id"], "amount": "1172200.00"},
    ]
    assert _get(client, "/receipts")[0]["appliedAmount"] in ("0", "0.00")


def test_confirmed_receipt_is_immutable(erp):
    client, created = erp
    receipt = _receipt(client, created, "100")
    patch = _call(
        client, created, "PATCH", f"/receipts/{receipt['id']}", {"amount": "200"}
    )
    assert _reason(patch) == "RECEIPT_CONFIRMED"
    delete = _call(client, created, "DELETE", f"/receipts/{receipt['id']}")
    assert _reason(delete) == "RECEIPT_CONFIRMED"
    draft = _receipt(client, created, "100", confirm=False)
    assert (
        _call(client, created, "DELETE", f"/receipts/{draft['id']}").status_code == 204
    )
