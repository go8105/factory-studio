"""FS-019b E-02 견적 API. 검증 항목마다 테스트를 나눈다."""

from uuid import uuid4

import pytest

BASE = "/api/v1/erp"


@pytest.fixture
def erp(guest_space):
    return guest_space[:2]


def _get(client, path: str):
    return client.get(f"{BASE}{path}").json()["data"]


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


def _id(client, path: str, field: str, code: str) -> int:
    rows = client.get(f"{BASE}{path}?limit=200").json()["data"]
    return next(r["id"] for r in rows if r[field] == code)


def _quote(client, no: str) -> dict:
    return next(q for q in _get(client, "/quotations") if q["quoteNo"] == no)


def _new_quote(client, created, no="Q-T01", **lines_override) -> dict:
    partner = _id(client, "/partners", "partnerCode", "C-001")
    item = _id(client, "/items", "itemCode", "FG-C100")
    quote = _call(
        client,
        created,
        "POST",
        "/quotations",
        {"quoteNo": no, "partnerId": partner, "quotedOn": "2026-09-24"},
    ).json()["data"]
    lines = lines_override.get("lines", [{"itemId": item, "quoteQty": "100"}])
    response = _call(
        client, created, "PUT", f"/quotations/{quote['id']}/lines", {"lines": lines}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _status(client, created, quote_id: int, status: str, reason=None):
    return _call(
        client,
        created,
        "POST",
        f"/quotations/{quote_id}/status",
        {"status": status, "reason": reason},
    )


def test_list_shows_latest_revision_only(erp):
    client, _ = erp
    quotes = _get(client, "/quotations")
    q2 = [q for q in quotes if q["quoteNo"] == "Q-0002"]
    assert [(q["revisionNo"], q["revisionCount"], q["isLatest"]) for q in q2] == [
        (2, 2, True)
    ]
    assert q2[0]["salesOrderId"] is not None


def test_revisions_return_history_read_only(erp):
    client, _ = erp
    revisions = _get(client, f"/quotations/{_quote(client, 'Q-0002')['id']}/revisions")
    assert [(r["revisionNo"], r["isLatest"], r["status"]) for r in revisions] == [
        (2, True, "accepted"),
        (1, False, "sent"),
    ]
    assert [h["status"] for h in revisions[1]["history"]] == [
        "draft",
        "confirmed",
        "sent",
    ]


def test_blank_price_uses_partner_price_and_marks_source(erp):
    client, created = erp
    quote = _new_quote(client, created)
    line = quote["lines"][0]
    assert (line["unitPrice"], line["priceSource"], line["unit"]) == (
        "850.0000",
        "partner_price",
        "EA",
    )
    assert line["amount"] == quote["totalAmount"] == "85000"
    assert [h["status"] for h in quote["history"]] == ["draft"]


def test_manual_price_and_discount(erp):
    client, created = erp
    item = _id(client, "/items", "itemCode", "FG-C100")
    quote = _new_quote(
        client,
        created,
        lines=[
            {"itemId": item, "quoteQty": "3", "unitPrice": "1001", "discountRate": "10"}
        ],
    )
    assert quote["lines"][0]["priceSource"] == "manual"
    assert quote["totalAmount"] == "2703"  # 3003 × 0.9 = 2702.7 → 2703


def test_missing_partner_price_requires_manual_price(erp):
    client, created = erp
    item = _id(client, "/items", "itemCode", "FG-T300")  # C-001 단가 없음
    quote = _new_quote(client, created)
    response = _call(
        client,
        created,
        "PUT",
        f"/quotations/{quote['id']}/lines",
        {"lines": [{"itemId": item, "quoteQty": "1"}]},
    )
    assert response.status_code == 400
    assert "거래처 단가" in response.json()["error"]["details"]["fields"]["lines"]


def test_supplier_partner_rejected(erp):
    client, created = erp
    supplier = _id(client, "/partners", "partnerCode", "V-001")
    response = _call(
        client,
        created,
        "POST",
        "/quotations",
        {"quoteNo": "Q-T02", "partnerId": supplier, "quotedOn": "2026-09-24"},
    )
    assert response.status_code == 400
    assert "partnerId" in response.json()["error"]["details"]["fields"]


def test_duplicate_quote_no_and_bad_valid_until(erp):
    client, created = erp
    partner = _id(client, "/partners", "partnerCode", "C-001")
    body = {"quoteNo": "Q-0001", "partnerId": partner, "quotedOn": "2026-09-24"}
    dup = _call(client, created, "POST", "/quotations", body)
    assert dup.json()["error"]["details"]["fields"] == {
        "quoteNo": "이미 사용 중인 견적번호입니다."
    }
    bad = _call(
        client,
        created,
        "POST",
        "/quotations",
        {**body, "quoteNo": "Q-T03", "validUntil": "2026-09-01"},
    )
    assert "validUntil" in bad.json()["error"]["details"]["fields"]


def test_confirm_locks_content_and_appends_history(erp):
    client, created = erp
    quote = _new_quote(client, created)
    confirmed = _status(client, created, quote["id"], "confirmed").json()["data"]
    assert [h["status"] for h in confirmed["history"]] == ["draft", "confirmed"]
    patch = _call(
        client, created, "PATCH", f"/quotations/{quote['id']}", {"remark": "x"}
    )
    assert patch.status_code == 409 and _reason(patch) == "QUOTATION_LOCKED"
    lines = _call(
        client, created, "PUT", f"/quotations/{quote['id']}/lines", {"lines": []}
    )
    assert _reason(lines) == "QUOTATION_LOCKED"


def test_empty_quote_cannot_confirm(erp):
    client, created = erp
    quote = _new_quote(client, created, lines=[])
    response = _status(client, created, quote["id"], "confirmed")
    assert response.status_code == 409 and _reason(response) == "EMPTY_QUOTATION"


def test_invalid_transition_and_reason_required(erp):
    client, created = erp
    quote = _new_quote(client, created)
    skip = _status(client, created, quote["id"], "accepted")
    assert skip.status_code == 409 and _reason(skip) == "INVALID_TRANSITION"
    no_reason = _status(client, created, quote["id"], "cancelled")
    assert no_reason.status_code == 400
    cancelled = _status(client, created, quote["id"], "cancelled", "고객 요청")
    assert cancelled.json()["data"]["history"][-1]["reason"] == "고객 요청"
    again = _status(client, created, quote["id"], "confirmed")
    assert _reason(again) == "INVALID_TRANSITION"


def test_revise_copies_lines_and_freezes_previous(erp):
    client, created = erp
    quote = _new_quote(client, created)
    _status(client, created, quote["id"], "confirmed")
    _status(client, created, quote["id"], "sent")
    revised = _call(client, created, "POST", f"/quotations/{quote['id']}/revise")
    assert revised.status_code == 201
    new = revised.json()["data"]
    assert (new["revisionNo"], new["status"], new["isLatest"]) == (2, "draft", True)
    assert [line["unitPrice"] for line in new["lines"]] == ["850.0000"]
    old = _status(client, created, quote["id"], "accepted")
    assert _reason(old) == "NOT_LATEST_REVISION"
    assert _quote(client, "Q-T01")["id"] == new["id"]


def test_draft_cannot_be_revised(erp):
    client, created = erp
    quote = _new_quote(client, created)
    response = _call(client, created, "POST", f"/quotations/{quote['id']}/revise")
    assert response.status_code == 409 and _reason(response) == "REVISE_NOT_ALLOWED"


def test_convert_creates_order_with_discounted_price(erp):
    client, created = erp
    item = _id(client, "/items", "itemCode", "FG-C100")
    quote = _new_quote(
        client,
        created,
        lines=[{"itemId": item, "quoteQty": "10", "discountRate": "10"}],
    )
    for status in ("confirmed", "sent"):
        _status(client, created, quote["id"], status)
    body = {"orderNo": "SO-T01", "orderedOn": "2026-09-25", "dueOn": "2026-10-10"}
    response = _call(
        client, created, "POST", f"/quotations/{quote['id']}/convert", body
    )
    assert response.status_code == 201, response.text
    order = response.json()["data"]
    assert (order["quoteNo"], order["status"], order["lines"][0]["unitPrice"]) == (
        "Q-T01",
        "open",
        "765.0000",
    )
    after = _quote(client, "Q-T01")
    assert (after["status"], after["salesOrderId"]) == ("accepted", order["id"])
    again = _call(
        client,
        created,
        "POST",
        f"/quotations/{quote['id']}/convert",
        {**body, "orderNo": "SO-T02"},
    )
    assert _reason(again) == "ALREADY_CONVERTED"


def test_draft_cannot_convert(erp):
    client, created = erp
    quote = _new_quote(client, created)
    body = {"orderNo": "SO-T01", "orderedOn": "2026-09-25", "dueOn": "2026-10-10"}
    response = _call(
        client, created, "POST", f"/quotations/{quote['id']}/convert", body
    )
    assert _reason(response) == "INVALID_TRANSITION"


def test_idempotent_replay_returns_same_quote(erp):
    client, created = erp
    partner = _id(client, "/partners", "partnerCode", "C-001")
    body = {"quoteNo": "Q-T09", "partnerId": partner, "quotedOn": "2026-09-24"}
    first = _call(client, created, "POST", "/quotations", body, key="k-q9")
    second = _call(client, created, "POST", "/quotations", body, key="k-q9")
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(_get(client, f"/quotations/{first.json()['data']['id']}/revisions")) == 1
