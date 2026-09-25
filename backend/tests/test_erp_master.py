"""FS-019a: ERP 기준정보 공통 계약. 각 검증 항목은 독립 테스트."""

import pytest
from fastapi.testclient import TestClient
from fs.main import create_app

BASE = "/api/v1/erp"
PARTNER = {
    "partnerCode": "NEW-C",
    "partnerName": "새 거래처",
    "partnerKind": "CUSTOMER",
}
ITEM = {
    "itemCode": "NEW-I",
    "name": "새 품목",
    "baseUnit": "EA",
    "itemType": "finished",
    "taxCategory": "TAXABLE",
}


def headers(data, key="write"):
    return {"X-CSRF-Token": data["csrfToken"], "Idempotency-Key": key}


@pytest.mark.parametrize(
    "resource", ["partners", "items", "partner-prices", "accounts", "posting-rules"]
)
def test_lists_require_authentication(resource):
    with TestClient(create_app()) as client:
        assert client.get(f"{BASE}/{resource}").status_code == 401


@pytest.mark.parametrize(
    "resource", ["partners", "items", "partner-prices", "accounts", "posting-rules"]
)
def test_lists_have_scoped_seed_rows(guest_space, resource):
    client, _, _ = guest_space
    body = client.get(f"{BASE}/{resource}").json()
    assert body["data"]
    assert body["page"]["total"] >= len(body["data"])


@pytest.mark.parametrize(
    "resource", ["partners", "items", "partner-prices", "accounts", "posting-rules"]
)
def test_offset_page(guest_space, resource):
    client, _, _ = guest_space
    first = client.get(f"{BASE}/{resource}?limit=1").json()
    second = client.get(f"{BASE}/{resource}?limit=1&offset=1").json()
    assert first["data"][0]["id"] != second["data"][0]["id"]
    assert first["page"]["total"] == second["page"]["total"]


@pytest.mark.parametrize(
    "resource", ["partners", "items", "partner-prices", "accounts", "posting-rules"]
)
def test_other_workspace_detail_is_hidden(guest_space, resource):
    client, _, _ = guest_space
    with TestClient(create_app(), base_url="https://testserver") as other:
        other.post("/api/v1/core/guest-sessions", headers={"Idempotency-Key": "other"})
        foreign = other.get(f"{BASE}/{resource}").json()["data"][0]["id"]
    assert client.get(f"{BASE}/{resource}/{foreign}").status_code == 404


@pytest.mark.parametrize(
    "resource", ["partners", "items", "partner-prices", "accounts", "posting-rules"]
)
def test_module_disabled_blocks_read(guest_space, resource):
    client, data, _ = guest_space
    client.patch(
        "/api/v1/core/workspace/modules/erp",
        json={"enabled": False},
        headers=headers(data),
    )
    response = client.get(f"{BASE}/{resource}")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_create(guest_space, resource, payload):
    client, data, _ = guest_space
    response = client.post(f"{BASE}/{resource}", json=payload, headers=headers(data))
    assert response.status_code == 201
    assert all(response.json()["data"][k] == v for k, v in payload.items())


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_write_requires_csrf(guest_space, resource, payload):
    client, _, _ = guest_space
    assert (
        client.post(
            f"{BASE}/{resource}", json=payload, headers={"Idempotency-Key": "a"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_write_requires_idempotency_key(guest_space, resource, payload):
    client, data, _ = guest_space
    r = client.post(
        f"{BASE}/{resource}", json=payload, headers={"X-CSRF-Token": data["csrfToken"]}
    )
    assert r.status_code == 400
    assert r.json()["error"]["details"]["fields"]


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_idempotent_create_replays(guest_space, resource, payload):
    client, data, _ = guest_space
    a = client.post(f"{BASE}/{resource}", json=payload, headers=headers(data))
    b = client.post(f"{BASE}/{resource}", json=payload, headers=headers(data))
    assert a.status_code == b.status_code == 201
    assert a.json() == b.json()


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_reused_key_rejects_changed_body(guest_space, resource, payload):
    client, data, _ = guest_space
    client.post(f"{BASE}/{resource}", json=payload, headers=headers(data))
    changed = {**payload, "isActive": False}
    assert (
        client.post(
            f"{BASE}/{resource}", json=changed, headers=headers(data)
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_scope_fields_rejected(guest_space, resource, payload):
    client, data, _ = guest_space
    r = client.post(
        f"{BASE}/{resource}",
        json={**payload, "workspaceId": data["workspaceId"]},
        headers=headers(data),
    )
    assert r.status_code == 400
    assert r.json()["error"]["details"]["fields"]


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_update_active(guest_space, resource, payload):
    client, data, _ = guest_space
    row = client.post(
        f"{BASE}/{resource}", json=payload, headers=headers(data, "create")
    ).json()["data"]
    r = client.patch(
        f"{BASE}/{resource}/{row['id']}",
        json={"isActive": False},
        headers=headers(data),
    )
    assert r.status_code == 200
    assert r.json()["data"]["isActive"] is False


@pytest.mark.parametrize(
    ("resource", "payload"), [("partners", PARTNER), ("items", ITEM)]
)
def test_delete_and_replay(guest_space, resource, payload):
    client, data, _ = guest_space
    row = client.post(
        f"{BASE}/{resource}", json=payload, headers=headers(data, "create")
    ).json()["data"]
    url = f"{BASE}/{resource}/{row['id']}"
    assert client.delete(url, headers=headers(data)).status_code == 204
    assert client.delete(url, headers=headers(data)).status_code == 204
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("resource", ["partners", "items"])
def test_referenced_delete_reports_counts(guest_space, resource):
    client, data, _ = guest_space
    row = client.get(f"{BASE}/{resource}").json()["data"][0]
    r = client.delete(f"{BASE}/{resource}/{row['id']}", headers=headers(data))
    assert r.status_code == 409
    body = r.json()["error"]
    assert body["code"] == "REFERENCED_BY_OTHERS"
    assert all(ref["count"] > 0 for ref in body["details"]["references"])


@pytest.mark.parametrize("resource", ["accounts", "posting-rules"])
def test_accounting_resources_have_no_write_route(guest_space, resource):
    client, data, _ = guest_space
    assert (
        client.post(f"{BASE}/{resource}", json={}, headers=headers(data)).status_code
        == 405
    )


def test_payment_terms_can_be_cleared(guest_space):
    client, data, _ = guest_space
    row = client.post(
        f"{BASE}/partners",
        json={**PARTNER, "paymentTermDays": 30},
        headers=headers(data, "create"),
    ).json()["data"]
    r = client.patch(
        f"{BASE}/partners/{row['id']}",
        json={"paymentTermDays": None},
        headers=headers(data),
    )
    assert r.json()["data"]["paymentTermDays"] is None


def test_reset_hides_old_ids(guest_space):
    client, data, _ = guest_space
    old = client.get(f"{BASE}/items").json()["data"][0]["id"]
    client.post("/api/v1/core/workspace/generations", headers=headers(data))
    assert client.get(f"{BASE}/items/{old}").status_code == 404


@pytest.mark.parametrize("resource", ["partners", "items", "partner-prices"])
def test_foreign_updates_are_hidden(guest_space, resource):
    client, data, _ = guest_space
    with TestClient(create_app(), base_url="https://testserver") as other:
        other.post("/api/v1/core/guest-sessions", headers={"Idempotency-Key": "other"})
        foreign = other.get(f"{BASE}/{resource}").json()["data"][0]["id"]
    r = client.patch(
        f"{BASE}/{resource}/{foreign}", json={"isActive": False}, headers=headers(data)
    )
    assert r.status_code == 404


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=201", "offset=-1", "sort=workspace_id:asc"]
)
def test_invalid_page_and_sort_include_fields(guest_space, query):
    client, _, _ = guest_space
    r = client.get(f"{BASE}/partners?{query}")
    assert r.status_code == 400
    assert r.json()["error"]["details"]["fields"]


def test_disabled_module_blocks_mutations(guest_space):
    client, data, _ = guest_space
    client.patch(
        "/api/v1/core/workspace/modules/erp",
        json={"enabled": False},
        headers=headers(data, "off"),
    )
    r = client.post(f"{BASE}/partners", json=PARTNER, headers=headers(data))
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "MODULE_DISABLED"
