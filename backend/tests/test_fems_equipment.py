"""FS-018a F-10 설비 API. 검증 항목마다 테스트를 나눈다."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template

BASE = "/api/v1/fems/equipments"
LOCATIONS = "/api/v1/fems/locations"


@pytest.fixture
def fems(clean_database: Engine, monkeypatch: pytest.MonkeyPatch):
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv(
        "SESSION_SECRET", "fs018-synthetic-test-secret-at-least-32-characters"
    )
    reset_engine()
    with engine.begin() as connection:
        create_template(connection, date(2026, 9, 24))
    with TestClient(create_app(), base_url="https://testserver") as client:
        created = client.post(
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "fems-guest"}
        ).json()["data"]
        yield client, created, engine
    reset_engine()


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _equipment_id(client, code: str) -> int:
    rows = client.get(BASE).json()["data"]
    return next(r["id"] for r in rows if r["equipmentCode"] == code)


def _first_location_id(client) -> int:
    return client.get(LOCATIONS).json()["data"][0]["id"]


def _other_guest(engine: Engine):
    with TestClient(create_app(), base_url="https://testserver") as other:
        created = other.post(
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "other-guest"}
        ).json()["data"]
        return other, created


def test_list_returns_seed_equipments_of_own_space(fems):
    client, _, _ = fems
    body = client.get(BASE).json()
    assert len(body["data"]) == 8
    assert body["page"] == {"offset": 0, "limit": 50, "total": 8}


def test_list_locations_returns_seed_locations(fems):
    client, _, _ = fems
    body = client.get(LOCATIONS).json()
    assert len(body["data"]) == 4
    assert all("id" in loc and "locationCode" in loc for loc in body["data"])


def test_list_rejects_unknown_sort_field(fems):
    client, _, _ = fems
    response = client.get(BASE, params={"sort": "workspace_id:asc"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_list_requires_session():
    with TestClient(create_app(), base_url="https://testserver") as anonymous:
        assert anonymous.get(BASE).status_code == 401


def test_other_space_equipment_is_not_found(fems):
    client, _, engine = fems
    other, _ = _other_guest(engine)
    foreign = other.get(BASE).json()["data"][0]["id"]
    assert client.get(f"{BASE}/{foreign}").status_code == 404


def test_create_requires_csrf(fems):
    client, _, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_NEW_01",
        "name": "신규 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    response = client.post(BASE, json=payload, headers={"Idempotency-Key": "no-csrf"})
    assert response.status_code == 403


def test_create_requires_idempotency_key(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_NEW_01",
        "name": "신규 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    response = client.post(
        BASE, json=payload, headers={"X-CSRF-Token": created["csrfToken"]}
    )
    assert response.status_code == 400


def test_create_stores_equipment(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_NEW_01",
        "name": "신규 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "create-1"))
    assert response.status_code == 201
    assert response.json()["data"]["equipmentCode"] == "EQ_NEW_01"
    assert client.get(BASE).json()["page"]["total"] == 9


def test_create_replay_returns_same_row(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_NEW_01",
        "name": "신규 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    first = client.post(BASE, json=payload, headers=_headers(created, "create-2"))
    second = client.post(BASE, json=payload, headers=_headers(created, "create-2"))
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert client.get(BASE).json()["page"]["total"] == 9


def test_create_same_key_other_body_conflicts(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_NEW_01",
        "name": "신규 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    client.post(BASE, json=payload, headers=_headers(created, "create-3"))
    response = client.post(
        BASE,
        json={**payload, "name": "다른 이름"},
        headers=_headers(created, "create-3"),
    )
    assert response.status_code == 422


def test_create_duplicate_code_is_field_error(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    seed_code = client.get(BASE).json()["data"][0]["equipmentCode"]
    payload = {
        "equipmentCode": seed_code,
        "name": "중복 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "dup"))
    assert response.status_code == 400
    assert "equipmentCode" in response.json()["error"]["details"]["fields"]


def test_create_rejects_foreign_location_id(fems):
    client, created, engine = fems
    other, _ = _other_guest(engine)
    foreign_loc_id = other.get(LOCATIONS).json()["data"][0]["id"]
    payload = {
        "equipmentCode": "EQ_FOREIGN_LOC",
        "name": "타 공간 설비",
        "equipmentType": "INJECTION",
        "locationId": foreign_loc_id,
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "foreign-loc"))
    assert response.status_code == 400
    assert "locationId" in response.json()["error"]["details"]["fields"]


def test_create_rejects_nonexistent_location_id(fems):
    client, created, _ = fems
    payload = {
        "equipmentCode": "EQ_NONEXISTENT",
        "name": "없는 공간 설비",
        "equipmentType": "INJECTION",
        "locationId": 9999999,
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "no-loc"))
    assert response.status_code == 400
    assert "locationId" in response.json()["error"]["details"]["fields"]


def test_create_rejects_scope_fields(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_SCOPE_ERR",
        "name": "스코프 위반",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
        "workspaceId": 1,
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "scope"))
    assert response.status_code == 400


def test_update_changes_name_and_type(fems):
    client, created, _ = fems
    eq_id = client.get(BASE).json()["data"][0]["id"]
    response = client.patch(
        f"{BASE}/{eq_id}",
        json={"name": "수정된 설비명", "equipmentType": "NEW_TYPE"},
        headers=_headers(created, "rename"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "수정된 설비명"
    assert response.json()["data"]["equipmentType"] == "NEW_TYPE"


def test_update_rejects_foreign_location_id(fems):
    client, created, engine = fems
    other, _ = _other_guest(engine)
    foreign_loc_id = other.get(LOCATIONS).json()["data"][0]["id"]
    eq_id = client.get(BASE).json()["data"][0]["id"]
    response = client.patch(
        f"{BASE}/{eq_id}",
        json={"locationId": foreign_loc_id},
        headers=_headers(created, "update-foreign-loc"),
    )
    assert response.status_code == 400
    assert "locationId" in response.json()["error"]["details"]["fields"]


def test_update_location_in_use_rejected(fems):
    client, created, _ = fems
    # (a) 시드 설비(계측기 있음)의 공간 변경은 409 LOCATION_IN_USE
    locations = client.get(LOCATIONS).json()["data"]
    first_eq = client.get(BASE).json()["data"][0]
    other_loc = next(
        loc["id"] for loc in locations if loc["id"] != first_eq["locationId"]
    )
    response = client.patch(
        f"{BASE}/{first_eq['id']}",
        json={"locationId": other_loc},
        headers=_headers(created, "chg-loc-in-use"),
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "PRECONDITION_NOT_MET"
    assert error["details"]["reason"] == "LOCATION_IN_USE"
    assert error["details"]["references"][0]["table"] == "fems.meter"
    assert error["details"]["references"][0]["label"] == "계측기"
    assert error["details"]["references"][0]["count"] > 0


def test_update_location_unreferenced_equipment_succeeds(fems):
    client, created, _ = fems
    # (b) 계측기 없는 설비의 공간 변경은 200
    locations = client.get(LOCATIONS).json()["data"]
    loc1 = locations[0]["id"]
    loc2 = locations[1]["id"]
    new_eq = client.post(
        BASE,
        json={
            "equipmentCode": "EQ_MOVE_TEST",
            "name": "이동 테스트 설비",
            "equipmentType": "INJECTION",
            "locationId": loc1,
        },
        headers=_headers(created, "create-move-test"),
    ).json()["data"]
    response = client.patch(
        f"{BASE}/{new_eq['id']}",
        json={"locationId": loc2},
        headers=_headers(created, "move-test-loc"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["locationId"] == loc2


def test_deactivate_referenced_equipment(fems):
    client, created, _ = fems
    first_eq = client.get(BASE).json()["data"][0]
    client.patch(
        f"{BASE}/{first_eq['id']}",
        json={"isActive": False},
        headers=_headers(created, "off"),
    )
    rows = client.get(BASE, params={"active": "true"}).json()["data"]
    assert first_eq["equipmentCode"] not in [r["equipmentCode"] for r in rows]


def test_delete_referenced_equipment_reports_counts(fems):
    client, created, _ = fems
    # 시드 1번 설비(EQ-INJ-01 등)는 meter, energy_allocation 등에 참조됨
    first_eq = client.get(BASE).json()["data"][0]
    response = client.delete(
        f"{BASE}/{first_eq['id']}", headers=_headers(created, "del-ref")
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "REFERENCED_BY_OTHERS"
    assert all(r["count"] > 0 for r in error["details"]["references"])
    referenced_tables = [r["table"] for r in error["details"]["references"]]
    assert any(
        t in referenced_tables
        for t in (
            "fems.meter",
            "fems.energy_target",
            "fems.energy_baseline",
            "fems.energy_allocation",
            "fems.production_record",
        )
    )


def test_delete_unreferenced_equipment(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_TO_DEL",
        "name": "삭제 대상 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    eq = client.post(BASE, json=payload, headers=_headers(created, "to-del")).json()
    eq_id = eq["data"]["id"]
    response = client.delete(f"{BASE}/{eq_id}", headers=_headers(created, "del"))
    assert response.status_code == 204
    assert client.get(f"{BASE}/{eq_id}").status_code == 404


def test_delete_replay_is_success(fems):
    client, created, _ = fems
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_TO_DEL_2",
        "name": "삭제 대상 설비 2",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    eq = client.post(BASE, json=payload, headers=_headers(created, "to-del-2")).json()
    eq_id = eq["data"]["id"]
    path = f"{BASE}/{eq_id}"
    assert client.delete(path, headers=_headers(created, "del-2")).status_code == 204
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
    loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_BLOCKED",
        "name": "차단 설비",
        "equipmentType": "INJECTION",
        "locationId": loc_id,
    }
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off-2"),
    )
    response = client.post(BASE, json=payload, headers=_headers(created, "blocked"))
    assert response.status_code == 409


def test_reset_moves_writes_to_new_generation(fems):
    client, created, engine = fems
    old_eq = client.get(BASE).json()["data"][0]
    client.post(
        "/api/v1/core/workspace/generations", headers=_headers(created, "reset")
    )
    assert client.get(f"{BASE}/{old_eq['id']}").status_code == 404

    # 새 세대에서 location_id 재조회
    new_loc_id = _first_location_id(client)
    payload = {
        "equipmentCode": "EQ_AFTER_RESET",
        "name": "리셋 후 설비",
        "equipmentType": "INJECTION",
        "locationId": new_loc_id,
    }
    client.post(BASE, json=payload, headers=_headers(created, "after-reset"))
    with engine.connect() as connection:
        generation = connection.execute(
            text(
                "SELECT e.generation_id=w.active_generation_id FROM fems.equipment e "
                "JOIN core.workspace w ON w.id=e.workspace_id WHERE e.equipment_code='EQ_AFTER_RESET'"
            )
        ).scalar_one()
    assert generation is True
