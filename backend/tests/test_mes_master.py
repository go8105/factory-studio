"""FS-020a MES 기준정보(M-10~M-13) API. 검증 항목마다 테스트를 나눈다."""

import pytest

BASE = "/api/v1/mes"


@pytest.fixture
def mes(guest_space):
    return guest_space[:2]


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _rows(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _by_code(client, path: str, field: str, code: str) -> dict:
    return next(r for r in _rows(client, path) if r[field] == code)


def _post(client, created, path: str, key: str, body: dict):
    return client.post(f"{BASE}{path}", json=body, headers=_headers(created, key))


def _patch(client, created, path: str, key: str, body: dict):
    return client.patch(f"{BASE}{path}", json=body, headers=_headers(created, key))


def _delete(client, created, path: str, key: str):
    return client.delete(f"{BASE}{path}", headers=_headers(created, key))


def _fields(response) -> dict:
    return response.json()["error"]["details"]["fields"]


# ---- 시드 ----
def test_seed_master_data(mes):
    client, _ = mes
    assert [s["siteCode"] for s in _rows(client, "/sites")] == ["S01"]
    # 유틸리티실(L-UTL)은 FEMS 전용이라 MES에 없다.
    assert {r["locationCode"] for r in _rows(client, "/locations")} == {
        "L-INJ",
        "L-ASM",
        "L-INS",
    }
    assert len(_rows(client, "/equipments")) == 8
    assert len(_rows(client, "/items")) == 6
    assert {p["processCode"] for p in _rows(client, "/processes")} == {
        "INJ",
        "ASM",
        "INS",
    }


def test_items_include_conversions(mes):
    client, _ = mes
    pin = _by_code(client, "/items", "itemCode", "RM-PIN")
    assert [(c["fromUnit"], c["toUnit"], c["factor"]) for c in pin["conversions"]] == [
        ("BOX", "EA", "10000.000000")
    ]


def test_processes_include_allowed_equipment(mes):
    client, _ = mes
    inj = _by_code(client, "/processes", "processCode", "INJ")
    codes = {e["id"]: e["equipmentCode"] for e in _rows(client, "/equipments")}
    assert {codes[i] for i in inj["equipmentIds"]} == {"INJ-01", "INJ-02", "INJ-03"}


# ---- M-10 사업장·공간 ----
def test_unknown_timezone_is_rejected(mes):
    client, created = mes
    response = _post(
        client,
        created,
        "/sites",
        "tz",
        {"siteCode": "S02", "name": "x", "timezone": "X/Y"},
    )
    assert response.status_code == 400
    assert "timezone" in _fields(response)


def test_site_with_locations_cannot_be_deleted(mes):
    client, created = mes
    site = _rows(client, "/sites")[0]
    response = _delete(client, created, f"/sites/{site['id']}", "del-site")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["references"][0]["label"] == "공간"


def test_location_parent_must_be_same_site_and_acyclic(mes):
    client, created = mes
    site = _rows(client, "/sites")[0]
    upper = _post(
        client,
        created,
        "/locations",
        "up",
        {
            "siteId": site["id"],
            "locationCode": "L-UP",
            "name": "상위",
            "kind": "building",
        },
    ).json()["data"]
    lower = _post(
        client,
        created,
        "/locations",
        "low",
        {
            "siteId": site["id"],
            "parentLocationId": upper["id"],
            "locationCode": "L-LOW",
            "name": "하위",
            "kind": "zone",
        },
    ).json()["data"]
    cycle = _patch(
        client,
        created,
        f"/locations/{upper['id']}",
        "cycle",
        {"parentLocationId": lower["id"]},
    )
    assert cycle.status_code == 400
    assert "parentLocationId" in _fields(cycle)
    other = _post(client, created, "/sites", "s2", {"siteCode": "S02", "name": "2공장"})
    cross = _post(
        client,
        created,
        "/locations",
        "cross",
        {
            "siteId": other.json()["data"]["id"],
            "parentLocationId": upper["id"],
            "locationCode": "L-X",
            "name": "x",
            "kind": "zone",
        },
    )
    assert cross.status_code == 400


def test_location_code_unique_within_site(mes):
    client, created = mes
    site = _rows(client, "/sites")[0]
    response = _post(
        client,
        created,
        "/locations",
        "dup-loc",
        {"siteId": site["id"], "locationCode": "L-INJ", "name": "x", "kind": "zone"},
    )
    assert response.status_code == 400
    assert "locationCode" in _fields(response)


def test_location_with_equipment_cannot_be_deleted(mes):
    client, created = mes
    inj = _by_code(client, "/locations", "locationCode", "L-INJ")
    response = _delete(client, created, f"/locations/{inj['id']}", "del-loc")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["references"][0]["label"] == "설비"


def test_location_site_cannot_change(mes):
    client, created = mes
    inj = _by_code(client, "/locations", "locationCode", "L-INJ")
    response = _patch(client, created, f"/locations/{inj['id']}", "site", {"siteId": 1})
    assert response.status_code == 400


# ---- M-11 설비 ----
def test_create_equipment_and_deactivate(mes):
    client, created = mes
    loc = _by_code(client, "/locations", "locationCode", "L-ASM")
    equipment = _post(
        client,
        created,
        "/equipments",
        "eq",
        {
            "locationId": loc["id"],
            "equipmentCode": "ASM-09",
            "name": "조립기 9호",
            "equipmentType": "ASM",
        },
    ).json()["data"]
    assert equipment["isActive"] is True
    off = _patch(
        client, created, f"/equipments/{equipment['id']}", "off", {"isActive": False}
    )
    assert off.json()["data"]["isActive"] is False


def test_duplicate_equipment_code_is_rejected(mes):
    client, created = mes
    loc = _by_code(client, "/locations", "locationCode", "L-ASM")
    response = _post(
        client,
        created,
        "/equipments",
        "dup-eq",
        {
            "locationId": loc["id"],
            "equipmentCode": "INJ-01",
            "name": "x",
            "equipmentType": "INJ",
        },
    )
    assert response.status_code == 400
    assert "equipmentCode" in _fields(response)


def test_equipment_in_use_cannot_be_deleted(mes):
    client, created = mes
    inj = _by_code(client, "/equipments", "equipmentCode", "INJ-01")
    response = _delete(client, created, f"/equipments/{inj['id']}", "del-eq")
    assert response.status_code == 409
    labels = {r["label"] for r in response.json()["error"]["details"]["references"]}
    assert labels == {"공정 허용 설비", "공정 실행"}


# ---- M-12 품목·단위 환산 ----
def test_item_base_unit_locked_when_referenced(mes):
    client, created = mes
    pin = _by_code(client, "/items", "itemCode", "RM-PIN")
    response = _patch(
        client, created, f"/items/{pin['id']}", "unit", {"baseUnit": "KG"}
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["reason"] == "UNIT_IN_USE"
    assert details["references"][0]["label"] == "단위 환산"


def test_new_item_base_unit_can_change(mes):
    client, created = mes
    item = _post(
        client,
        created,
        "/items",
        "item",
        {"itemCode": "RM-NEW", "name": "신규 자재", "itemType": "raw"},
    ).json()["data"]
    response = _patch(
        client, created, f"/items/{item['id']}", "unit2", {"baseUnit": "KG"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["baseUnit"] == "KG"


def test_item_in_use_cannot_be_deleted(mes):
    client, created = mes
    item = _by_code(client, "/items", "itemCode", "FG-C100")
    response = _delete(client, created, f"/items/{item['id']}", "del-item")
    assert response.status_code == 409
    labels = {r["label"] for r in response.json()["error"]["details"]["references"]}
    assert {"공정 경로", "작업지시"} <= labels


def test_conversion_to_unit_is_item_base_unit(mes):
    client, created = mes
    pbt = _by_code(client, "/items", "itemCode", "RM-PBT")
    response = _post(
        client,
        created,
        f"/items/{pbt['id']}/conversions",
        "conv",
        {"fromUnit": "BAG", "factor": "25"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["toUnit"] == "KG"


def test_conversion_from_base_unit_is_rejected(mes):
    client, created = mes
    pbt = _by_code(client, "/items", "itemCode", "RM-PBT")
    response = _post(
        client,
        created,
        f"/items/{pbt['id']}/conversions",
        "same",
        {"fromUnit": "KG", "factor": "1"},
    )
    assert response.status_code == 400
    assert "fromUnit" in _fields(response)


def test_conversion_zero_factor_and_duplicate(mes):
    client, created = mes
    pin = _by_code(client, "/items", "itemCode", "RM-PIN")
    zero = _post(
        client,
        created,
        f"/items/{pin['id']}/conversions",
        "zero",
        {"fromUnit": "SET", "factor": "0"},
    )
    assert zero.status_code == 400
    assert "factor" in _fields(zero)
    dup = _post(
        client,
        created,
        f"/items/{pin['id']}/conversions",
        "dup",
        {"fromUnit": "BOX", "factor": "5"},
    )
    assert dup.status_code == 400
    assert "fromUnit" in _fields(dup)


def test_conversion_must_belong_to_item(mes):
    client, created = mes
    pin = _by_code(client, "/items", "itemCode", "RM-PIN")
    pbt = _by_code(client, "/items", "itemCode", "RM-PBT")
    conversion = pin["conversions"][0]
    response = _delete(
        client, created, f"/items/{pbt['id']}/conversions/{conversion['id']}", "wrong"
    )
    assert response.status_code == 404
    ok = _delete(
        client, created, f"/items/{pin['id']}/conversions/{conversion['id']}", "right"
    )
    assert ok.status_code == 204


# ---- M-13 공정 ----
def test_create_process_with_equipment(mes):
    client, created = mes
    ids = [
        e["id"]
        for e in _rows(client, "/equipments")
        if e["equipmentCode"] in ("ASM-01", "INS-01")
    ]
    process = _post(
        client,
        created,
        "/processes",
        "proc",
        {
            "processCode": "PKG",
            "name": "포장",
            "processType": "PKG",
            "equipmentIds": ids,
        },
    ).json()["data"]
    assert process["equipmentIds"] == sorted(ids)


def test_process_equipment_is_replaced(mes):
    client, created = mes
    inj = _by_code(client, "/processes", "processCode", "INJ")
    keep = inj["equipmentIds"][:1]
    response = _patch(
        client, created, f"/processes/{inj['id']}", "replace", {"equipmentIds": keep}
    )
    assert response.status_code == 200
    assert response.json()["data"]["equipmentIds"] == keep


def test_unknown_equipment_is_rejected(mes):
    client, created = mes
    inj = _by_code(client, "/processes", "processCode", "INJ")
    response = _patch(
        client, created, f"/processes/{inj['id']}", "bad-eq", {"equipmentIds": [999999]}
    )
    assert response.status_code == 400
    assert "equipmentIds" in _fields(response)


def test_process_in_route_cannot_be_deleted(mes):
    client, created = mes
    inj = _by_code(client, "/processes", "processCode", "INJ")
    response = _delete(client, created, f"/processes/{inj['id']}", "del-proc")
    assert response.status_code == 409
    assert (
        response.json()["error"]["details"]["references"][0]["label"]
        == "공정 경로 단계"
    )


def test_unused_process_is_deleted_with_links(mes):
    client, created = mes
    eq = _rows(client, "/equipments")[0]
    process = _post(
        client,
        created,
        "/processes",
        "tmp",
        {
            "processCode": "TMP",
            "name": "임시",
            "processType": "TMP",
            "equipmentIds": [eq["id"]],
        },
    ).json()["data"]
    response = _delete(client, created, f"/processes/{process['id']}", "del-tmp")
    assert response.status_code == 204
    assert len(_rows(client, "/processes")) == 3


# ---- 공통 ----
def test_create_is_idempotent(mes):
    client, created = mes
    body = {"itemCode": "RM-IDEM", "name": "x"}
    first = _post(client, created, "/items", "same", body)
    second = _post(client, created, "/items", "same", body)
    assert first.json() == second.json()
    assert len(_rows(client, "/items")) == 7


def test_create_requires_csrf(mes):
    client, _ = mes
    response = client.post(
        f"{BASE}/items",
        json={"itemCode": "RM-X", "name": "x"},
        headers={"Idempotency-Key": "k"},
    )
    assert response.status_code == 403


def test_not_found(mes):
    client, _ = mes
    assert client.get(f"{BASE}/items/999999").status_code == 404


def test_disabled_module_blocks_mes(mes):
    client, created = mes
    client.patch(
        "/api/v1/core/workspace/modules/mes",
        json={"enabled": False},
        headers=_headers(created, "mes-off"),
    )
    response = client.get(f"{BASE}/items")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"
