"""FS-018a F-11 에너지원 API. 검증 항목마다 테스트를 나눈다."""

import pytest
from fastapi.testclient import TestClient
from fs.main import create_app
from sqlalchemy import Engine, text

BASE = "/api/v1/fems/energy-sources"
NEW = {
    "sourceCode": "STEAM",
    "name": "스팀",
    "sourceKind": "HEAT",
    "measureUnit": "ton",
}


@pytest.fixture
def fems(guest_space):
    return guest_space


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _source_id(client, code: str) -> int:
    rows = client.get(BASE).json()["data"]
    return next(r["id"] for r in rows if r["sourceCode"] == code)


def _other_guest(engine: Engine):
    with TestClient(create_app(), base_url="https://testserver") as other:
        created = other.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "테스트 게스트"},
            headers={"Idempotency-Key": "other-guest"},
        ).json()["data"]
        return other, created


def test_list_returns_seed_sources_of_own_space(fems):
    client, _, _ = fems
    body = client.get(BASE).json()
    assert [r["sourceCode"] for r in body["data"]] == ["ELEC", "GAS", "WATER"]
    assert body["page"] == {"offset": 0, "limit": 50, "total": 3}


def test_list_rejects_unknown_sort_field(fems):
    client, _, _ = fems
    response = client.get(BASE, params={"sort": "workspace_id:asc"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_list_requires_session():
    with TestClient(create_app(), base_url="https://testserver") as anonymous:
        assert anonymous.get(BASE).status_code == 401


def test_other_space_source_is_not_found(fems):
    client, _, engine = fems
    other, _ = _other_guest(engine)
    foreign = other.get(BASE).json()["data"][0]["id"]
    assert client.get(f"{BASE}/{foreign}").status_code == 404


def test_create_requires_csrf(fems):
    client, _, _ = fems
    response = client.post(BASE, json=NEW, headers={"Idempotency-Key": "no-csrf"})
    assert response.status_code == 403


def test_create_requires_idempotency_key(fems):
    client, created, _ = fems
    response = client.post(
        BASE, json=NEW, headers={"X-CSRF-Token": created["csrfToken"]}
    )
    assert response.status_code == 400


def test_create_stores_source(fems):
    client, created, _ = fems
    response = client.post(BASE, json=NEW, headers=_headers(created, "create-1"))
    assert response.status_code == 201
    assert response.json()["data"]["sourceCode"] == "STEAM"
    assert client.get(BASE).json()["page"]["total"] == 4


def test_create_replay_returns_same_row(fems):
    client, created, _ = fems
    first = client.post(BASE, json=NEW, headers=_headers(created, "create-2"))
    second = client.post(BASE, json=NEW, headers=_headers(created, "create-2"))
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert client.get(BASE).json()["page"]["total"] == 4


def test_create_same_key_other_body_conflicts(fems):
    client, created, _ = fems
    client.post(BASE, json=NEW, headers=_headers(created, "create-3"))
    response = client.post(
        BASE, json={**NEW, "name": "증기"}, headers=_headers(created, "create-3")
    )
    assert response.status_code == 422


def test_create_duplicate_code_is_field_error(fems):
    client, created, _ = fems
    response = client.post(
        BASE, json={**NEW, "sourceCode": "ELEC"}, headers=_headers(created, "dup")
    )
    assert response.status_code == 400
    assert "sourceCode" in response.json()["error"]["details"]["fields"]


def test_create_rejects_unknown_kind(fems):
    client, created, _ = fems
    response = client.post(
        BASE, json={**NEW, "sourceKind": "NUCLEAR"}, headers=_headers(created, "kind")
    )
    assert response.status_code == 400


def test_create_rejects_scope_fields(fems):
    client, created, _ = fems
    response = client.post(
        BASE, json={**NEW, "workspaceId": 1}, headers=_headers(created, "scope")
    )
    assert response.status_code == 400


def test_update_changes_name(fems):
    client, created, _ = fems
    source = _source_id(client, "GAS")
    response = client.patch(
        f"{BASE}/{source}", json={"name": "LNG"}, headers=_headers(created, "rename")
    )
    assert response.json()["data"]["name"] == "LNG"


def test_update_unit_of_referenced_source_is_blocked(fems):
    client, created, _ = fems
    source = _source_id(client, "ELEC")
    response = client.patch(
        f"{BASE}/{source}",
        json={"measureUnit": "ton"},
        headers=_headers(created, "unit"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "UNIT_IN_USE"


def test_update_unit_of_unreferenced_source_is_allowed(fems):
    client, created, _ = fems
    source = client.post(BASE, json=NEW, headers=_headers(created, "new-unit")).json()
    response = client.patch(
        f"{BASE}/{source['data']['id']}",
        json={"measureUnit": "kWh"},
        headers=_headers(created, "unit-free"),
    )
    assert response.json()["data"]["measureUnit"] == "kWh"


def test_deactivate_referenced_source(fems):
    client, created, _ = fems
    source = _source_id(client, "WATER")
    client.patch(
        f"{BASE}/{source}", json={"isActive": False}, headers=_headers(created, "off")
    )
    rows = client.get(BASE, params={"active": "true"}).json()["data"]
    assert "WATER" not in [r["sourceCode"] for r in rows]


def test_delete_referenced_source_reports_counts(fems):
    client, created, _ = fems
    source = _source_id(client, "ELEC")
    response = client.delete(f"{BASE}/{source}", headers=_headers(created, "del-ref"))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "REFERENCED_BY_OTHERS"
    assert all(r["count"] > 0 for r in error["details"]["references"])
    assert "fems.meter_channel" in [r["table"] for r in error["details"]["references"]]


def test_delete_unreferenced_source(fems):
    client, created, _ = fems
    source = client.post(BASE, json=NEW, headers=_headers(created, "to-del")).json()
    response = client.delete(
        f"{BASE}/{source['data']['id']}", headers=_headers(created, "del")
    )
    assert response.status_code == 204
    assert client.get(f"{BASE}/{source['data']['id']}").status_code == 404


def test_delete_replay_is_success(fems):
    client, created, _ = fems
    source = client.post(BASE, json=NEW, headers=_headers(created, "to-del-2")).json()
    path = f"{BASE}/{source['data']['id']}"
    client.delete(path, headers=_headers(created, "del-2"))
    assert client.delete(path, headers=_headers(created, "del-2")).status_code == 204


def test_disabled_module_blocks_reads(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off"),
    )
    response = client.get(BASE)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"


def test_disabled_module_blocks_writes(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off-2"),
    )
    response = client.post(BASE, json=NEW, headers=_headers(created, "blocked"))
    assert response.status_code == 409


def test_reset_moves_writes_to_new_generation(fems):
    client, created, engine = fems
    old = _source_id(client, "GAS")
    client.post(
        "/api/v1/core/workspace/generations", headers=_headers(created, "reset")
    )
    assert client.get(f"{BASE}/{old}").status_code == 404
    client.post(BASE, json=NEW, headers=_headers(created, "after-reset"))
    with engine.connect() as connection:
        generation = connection.execute(
            text(
                "SELECT s.generation_id=w.active_generation_id FROM fems.energy_source s "
                "JOIN core.workspace w ON w.id=s.workspace_id WHERE s.source_code='STEAM'"
            )
        ).scalar_one()
    assert generation is True
