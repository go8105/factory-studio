import pytest

BASE = "/api/v1/erp/items"


def headers(data, key="write"):
    return {"X-CSRF-Token": data["csrfToken"], "Idempotency-Key": key}


@pytest.fixture
def conversion(guest_space):
    client, data, _ = guest_space
    row = client.post(
        BASE,
        json={"itemCode": "CONV-TEST", "name": "환산 테스트", "taxCategory": "TAXABLE"},
        headers=headers(data, "item"),
    ).json()["data"]
    return client, data, row["id"]


def test_conversion_derives_base_unit(conversion):
    client, data, item = conversion
    r = client.post(
        f"{BASE}/{item}/conversions",
        json={"fromUnit": "BOX", "factor": "12.5"},
        headers=headers(data),
    )
    assert r.status_code == 201
    assert r.json()["data"]["toUnit"] == "EA"
    assert r.json()["data"]["factor"] == "12.500000"


@pytest.mark.parametrize(
    "payload",
    [
        {"fromUnit": "EA", "factor": "1"},
        {"fromUnit": "BOX", "factor": "0"},
        {"fromUnit": "BOX", "factor": "1.0000001"},
        {"fromUnit": "BOX", "factor": "1", "toUnit": "KG"},
    ],
)
def test_invalid_conversion_fields(conversion, payload):
    client, data, item = conversion
    r = client.post(f"{BASE}/{item}/conversions", json=payload, headers=headers(data))
    assert r.status_code == 400
    assert r.json()["error"]["details"]["fields"]


def test_conversion_update(conversion):
    client, data, item = conversion
    row = client.post(
        f"{BASE}/{item}/conversions",
        json={"fromUnit": "BOX", "factor": "12"},
        headers=headers(data, "create"),
    ).json()["data"]
    r = client.patch(
        f"{BASE}/{item}/conversions/{row['id']}",
        json={"factor": "24"},
        headers=headers(data),
    )
    assert r.json()["data"]["factor"] == "24.000000"


def test_conversion_delete(conversion):
    client, data, item = conversion
    row = client.post(
        f"{BASE}/{item}/conversions",
        json={"fromUnit": "BOX", "factor": "12"},
        headers=headers(data, "create"),
    ).json()["data"]
    assert (
        client.delete(
            f"{BASE}/{item}/conversions/{row['id']}", headers=headers(data)
        ).status_code
        == 204
    )


def test_referenced_base_unit_change_blocked(conversion):
    client, data, item = conversion
    client.post(
        f"{BASE}/{item}/conversions",
        json={"fromUnit": "BOX", "factor": "12"},
        headers=headers(data, "create"),
    )
    r = client.patch(f"{BASE}/{item}", json={"baseUnit": "KG"}, headers=headers(data))
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "UNIT_IN_USE"
