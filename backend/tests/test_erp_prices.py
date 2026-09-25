import pytest

BASE = "/api/v1/erp"


def headers(data, key="write"):
    return {"X-CSRF-Token": data["csrfToken"], "Idempotency-Key": key}


@pytest.fixture
def pricing(guest_space):
    client, data, _ = guest_space
    partner = client.post(
        BASE + "/partners",
        json={
            "partnerCode": "P-NEW",
            "partnerName": "새 거래처",
            "partnerKind": "CUSTOMER",
        },
        headers=headers(data, "partner"),
    ).json()["data"]
    item = client.get(BASE + "/items").json()["data"][0]
    payload = {
        "partnerId": partner["id"],
        "itemId": item["id"],
        "unitPrice": "123.4567",
        "effectiveFrom": "2026-01",
        "effectiveTo": "2026-03",
    }
    return client, data, payload


def test_create_decimal_price(pricing):
    client, data, payload = pricing
    r = client.post(BASE + "/partner-prices", json=payload, headers=headers(data))
    assert r.status_code == 201
    assert r.json()["data"]["unitPrice"] == "123.4567"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2025-12", "2026-01"),
        ("2026-03", "2026-04"),
        ("2026-02", None),
        ("2025-01", None),
    ],
)
def test_overlapping_months_rejected(pricing, start, end):
    client, data, payload = pricing
    client.post(BASE + "/partner-prices", json=payload, headers=headers(data, "first"))
    r = client.post(
        BASE + "/partner-prices",
        json={**payload, "effectiveFrom": start, "effectiveTo": end},
        headers=headers(data),
    )
    assert r.status_code == 409
    assert r.json()["error"]["details"]["references"][0]["count"] == 1


def test_adjacent_month_is_allowed(pricing):
    client, data, payload = pricing
    client.post(BASE + "/partner-prices", json=payload, headers=headers(data, "first"))
    r = client.post(
        BASE + "/partner-prices",
        json={**payload, "effectiveFrom": "2026-04", "effectiveTo": None},
        headers=headers(data),
    )
    assert r.status_code == 201


def test_update_excludes_itself(pricing):
    client, data, payload = pricing
    row = client.post(
        BASE + "/partner-prices", json=payload, headers=headers(data, "first")
    ).json()["data"]
    r = client.patch(
        f"{BASE}/partner-prices/{row['id']}",
        json={"unitPrice": "0"},
        headers=headers(data),
    )
    assert r.json()["data"]["unitPrice"] == "0.0000"


@pytest.mark.parametrize(
    "change",
    [
        {"unitPrice": "-1"},
        {"unitPrice": "1.00001"},
        {"effectiveFrom": "2026-13"},
        {"effectiveTo": "2025-12"},
        {"partnerId": 999999},
    ],
)
def test_invalid_price_has_fields(pricing, change):
    client, data, payload = pricing
    r = client.post(
        BASE + "/partner-prices", json={**payload, **change}, headers=headers(data)
    )
    assert r.status_code == 400
    assert r.json()["error"]["details"]["fields"]


def test_delete_price(pricing):
    client, data, payload = pricing
    row = client.post(
        BASE + "/partner-prices", json=payload, headers=headers(data, "first")
    ).json()["data"]
    assert (
        client.delete(
            f"{BASE}/partner-prices/{row['id']}", headers=headers(data)
        ).status_code
        == 204
    )


def test_update_cannot_overlap_another_price(pricing):
    client, data, payload = pricing
    client.post(BASE + "/partner-prices", json=payload, headers=headers(data, "first"))
    row = client.post(
        BASE + "/partner-prices",
        json={**payload, "effectiveFrom": "2026-04", "effectiveTo": None},
        headers=headers(data, "second"),
    ).json()["data"]
    r = client.patch(
        f"{BASE}/partner-prices/{row['id']}",
        json={"effectiveFrom": "2026-03"},
        headers=headers(data),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PERIOD_OVERLAP"


def test_failed_overlap_does_not_change_price(pricing):
    client, data, payload = pricing
    client.post(BASE + "/partner-prices", json=payload, headers=headers(data, "first"))
    row = client.post(
        BASE + "/partner-prices",
        json={**payload, "effectiveFrom": "2026-04", "effectiveTo": None},
        headers=headers(data, "second"),
    ).json()["data"]
    url = f"{BASE}/partner-prices/{row['id']}"
    client.patch(url, json={"effectiveFrom": "2026-03"}, headers=headers(data))
    assert client.get(url).json()["data"]["effectiveFrom"] == "2026-04"
