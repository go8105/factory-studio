"""FS-018m F-09 사업장·공간 API. 검증 항목마다 테스트를 나눈다."""

import pytest

SITES = "/api/v1/fems/sites"
LOCATIONS = "/api/v1/fems/locations"


@pytest.fixture
def fems(guest_space):
    return guest_space[:2]


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _site(client) -> dict:
    return client.get(SITES).json()["data"][0]


def _location(client, code: str) -> dict:
    rows = client.get(LOCATIONS).json()["data"]
    return next(r for r in rows if r["locationCode"] == code)


def _new_site(client, created, key: str, **override) -> dict:
    response = client.post(
        SITES,
        json={"siteCode": "S02", "name": "제2공장", **override},
        headers=_headers(created, key),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _new_location(client, created, key: str, **override) -> dict:
    payload = {
        "siteId": _site(client)["id"],
        "locationCode": "L-NEW",
        "name": "신규 구역",
        "kind": "zone",
        **override,
    }
    response = client.post(LOCATIONS, json=payload, headers=_headers(created, key))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_seed_site_and_locations(fems):
    client, _ = fems
    site = _site(client)
    assert (site["siteCode"], site["timezone"]) == ("S01", "Asia/Seoul")
    locations = client.get(LOCATIONS).json()["data"]
    assert {r["locationCode"] for r in locations} == {
        "L-INJ",
        "L-ASM",
        "L-INS",
        "L-UTL",
    }
    assert all(r["siteId"] == site["id"] for r in locations)


def test_create_site_defaults_to_seoul(fems):
    client, created = fems
    site = _new_site(client, created, "site")
    assert site["timezone"] == "Asia/Seoul"


def test_unknown_timezone_is_rejected(fems):
    client, created = fems
    response = client.post(
        SITES,
        json={"siteCode": "S02", "name": "x", "timezone": "Mars/Base"},
        headers=_headers(created, "tz"),
    )
    assert response.status_code == 400
    assert "timezone" in response.json()["error"]["details"]["fields"]


def test_duplicate_site_code_is_rejected(fems):
    client, created = fems
    response = client.post(
        SITES, json={"siteCode": "S01", "name": "x"}, headers=_headers(created, "dup")
    )
    assert response.status_code == 400
    assert "siteCode" in response.json()["error"]["details"]["fields"]


def test_timezone_of_site_with_records_is_locked(fems):
    client, created = fems
    site = _site(client)
    response = client.patch(
        f"{SITES}/{site['id']}",
        json={"timezone": "Asia/Tokyo"},
        headers=_headers(created, "tz-lock"),
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["reason"] == "TIMEZONE_IN_USE"
    assert {r["table"] for r in details["references"]} == {
        "fems.energy_reading",
        "fems.energy_allocation",
        "fems.production_record",
    }


def test_site_with_records_can_be_renamed(fems):
    client, created = fems
    site = _site(client)
    response = client.patch(
        f"{SITES}/{site['id']}",
        json={"name": "본사 공장"},
        headers=_headers(created, "rename"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "본사 공장"


def test_empty_site_timezone_can_change(fems):
    client, created = fems
    site = _new_site(client, created, "fresh")
    response = client.patch(
        f"{SITES}/{site['id']}",
        json={"timezone": "Asia/Tokyo"},
        headers=_headers(created, "tz-fresh"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["timezone"] == "Asia/Tokyo"


def test_site_with_locations_cannot_be_deleted(fems):
    client, created = fems
    site = _site(client)
    response = client.delete(f"{SITES}/{site['id']}", headers=_headers(created, "del"))
    assert response.status_code == 409
    labels = {r["label"] for r in response.json()["error"]["details"]["references"]}
    assert {"공간", "계측기"} <= labels


def test_empty_site_can_be_deleted(fems):
    client, created = fems
    site = _new_site(client, created, "to-del")
    response = client.delete(
        f"{SITES}/{site['id']}", headers=_headers(created, "del-fresh")
    )
    assert response.status_code == 204
    assert len(client.get(SITES).json()["data"]) == 1


def test_create_site_is_idempotent(fems):
    client, created = fems
    payload = {"siteCode": "S09", "name": "x"}
    first = client.post(SITES, json=payload, headers=_headers(created, "same"))
    second = client.post(SITES, json=payload, headers=_headers(created, "same"))
    assert first.json() == second.json()
    assert len(client.get(SITES).json()["data"]) == 2


def test_create_site_requires_csrf(fems):
    client, _ = fems
    response = client.post(
        SITES, json={"siteCode": "S09", "name": "x"}, headers={"Idempotency-Key": "k"}
    )
    assert response.status_code == 403


def test_create_location_under_parent(fems):
    client, created = fems
    parent = _location(client, "L-UTL")
    location = _new_location(client, created, "loc", parentLocationId=parent["id"])
    assert location["parentLocationId"] == parent["id"]


def test_location_code_is_unique_within_site_only(fems):
    client, created = fems
    response = client.post(
        LOCATIONS,
        json={
            "siteId": _site(client)["id"],
            "locationCode": "L-INJ",
            "name": "x",
            "kind": "zone",
        },
        headers=_headers(created, "dup-loc"),
    )
    assert response.status_code == 400
    assert "locationCode" in response.json()["error"]["details"]["fields"]
    other = _new_site(client, created, "other-site")
    _new_location(
        client, created, "same-code", siteId=other["id"], locationCode="L-INJ"
    )


def test_parent_from_other_site_is_rejected(fems):
    client, created = fems
    other = _new_site(client, created, "other")
    response = client.post(
        LOCATIONS,
        json={
            "siteId": other["id"],
            "parentLocationId": _location(client, "L-UTL")["id"],
            "locationCode": "L-X",
            "name": "x",
            "kind": "zone",
        },
        headers=_headers(created, "cross"),
    )
    assert response.status_code == 400
    assert "parentLocationId" in response.json()["error"]["details"]["fields"]


def test_location_cycle_is_rejected(fems):
    client, created = fems
    upper = _new_location(client, created, "upper", locationCode="L-UP")
    lower = _new_location(
        client, created, "lower", locationCode="L-LOW", parentLocationId=upper["id"]
    )
    response = client.patch(
        f"{LOCATIONS}/{upper['id']}",
        json={"parentLocationId": lower["id"]},
        headers=_headers(created, "cycle"),
    )
    assert response.status_code == 400
    assert "parentLocationId" in response.json()["error"]["details"]["fields"]


def test_location_site_cannot_change(fems):
    client, created = fems
    location = _location(client, "L-INJ")
    response = client.patch(
        f"{LOCATIONS}/{location['id']}",
        json={"siteId": 999},
        headers=_headers(created, "site-change"),
    )
    assert response.status_code == 400


def test_location_rename_and_kind(fems):
    client, created = fems
    location = _location(client, "L-INJ")
    response = client.patch(
        f"{LOCATIONS}/{location['id']}",
        json={"name": "사출 1동", "kind": "building"},
        headers=_headers(created, "loc-rename"),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["name"], data["kind"]) == ("사출 1동", "building")


def test_location_with_equipment_cannot_be_deleted(fems):
    client, created = fems
    location = _location(client, "L-INJ")
    response = client.delete(
        f"{LOCATIONS}/{location['id']}", headers=_headers(created, "loc-del")
    )
    assert response.status_code == 409
    labels = {r["label"] for r in response.json()["error"]["details"]["references"]}
    assert labels == {"설비", "계측기"}


def test_empty_location_can_be_deleted(fems):
    client, created = fems
    location = _new_location(client, created, "loc-fresh")
    response = client.delete(
        f"{LOCATIONS}/{location['id']}", headers=_headers(created, "loc-del-fresh")
    )
    assert response.status_code == 204
    assert len(client.get(LOCATIONS).json()["data"]) == 4


def test_disabled_module_blocks_sites(fems):
    client, created = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off"),
    )
    response = client.get(SITES)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"
