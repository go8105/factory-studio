"""FS-018l F-12 계측기·채널 API. 검증 항목마다 테스트를 나눈다."""

import pytest

BASE = "/api/v1/fems/meters"


@pytest.fixture
def fems(guest_space):
    return guest_space[:2]


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _meter(client, code: str) -> dict:
    return next(m for m in client.get(BASE).json()["data"] if m["meterCode"] == code)


def _location(client, code: str) -> int:
    rows = client.get("/api/v1/fems/locations").json()["data"]
    return next(r["id"] for r in rows if r["locationCode"] == code)


def _equipment(client, code: str) -> int:
    rows = client.get("/api/v1/fems/equipments").json()["data"]
    return next(r["id"] for r in rows if r["equipmentCode"] == code)


def _source(client, code: str) -> int:
    rows = client.get("/api/v1/fems/energy-sources").json()["data"]
    return next(r["id"] for r in rows if r["sourceCode"] == code)


def _create(client, created, key: str, **override) -> dict:
    payload = {
        "meterCode": "M-NEW",
        "name": "신규 계측기",
        "locationId": _location(client, "L-UTL"),
        "scopeKind": "factory",
        **override,
    }
    response = client.post(BASE, json=payload, headers=_headers(created, key))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _channel_payload(client, **override) -> dict:
    return {
        "channelCode": "CH-NEW",
        "name": "신규 채널",
        "energySourceId": _source(client, "ELEC"),
        "measurementKind": "CUMULATIVE",
        "unit": "kWh",
        **override,
    }


def test_list_has_hierarchy_and_usage(fems):
    client, _ = fems
    meters = client.get(BASE).json()["data"]
    assert len(meters) == 11
    main = _meter(client, "M-MAIN")
    inj = _meter(client, "M-INJ-01")
    assert (main["parentMeterId"], main["scopeKind"]) == (None, "site_total")
    assert inj["parentMeterId"] == main["id"]
    assert inj["equipmentId"] == _equipment(client, "INJ-01")
    assert (inj["channelCount"], inj["observed"]) == (1, True)
    assert inj["channels"][0]["observed"] is True


def test_create_derives_site_from_location(fems):
    client, created = fems
    meter = _create(client, created, "create")
    assert meter["siteId"] == _meter(client, "M-MAIN")["siteId"]
    assert (meter["channelCount"], meter["observed"]) == (0, False)


def test_invalid_location_is_rejected(fems):
    client, created = fems
    response = client.post(
        BASE,
        json={
            "meterCode": "M-X",
            "name": "x",
            "locationId": 999999,
            "scopeKind": "factory",
        },
        headers=_headers(created, "bad-loc"),
    )
    assert response.status_code == 400
    assert "locationId" in response.json()["error"]["details"]["fields"]


def test_equipment_must_be_in_same_location(fems):
    client, created = fems
    response = client.post(
        BASE,
        json={
            "meterCode": "M-X",
            "name": "x",
            "locationId": _location(client, "L-UTL"),
            "equipmentId": _equipment(client, "INJ-01"),
            "scopeKind": "factory",
        },
        headers=_headers(created, "bad-eq"),
    )
    assert response.status_code == 400
    assert "equipmentId" in response.json()["error"]["details"]["fields"]


def test_duplicate_meter_code_is_rejected(fems):
    client, created = fems
    response = client.post(
        BASE,
        json={
            "meterCode": "M-MAIN",
            "name": "x",
            "locationId": _location(client, "L-UTL"),
            "scopeKind": "factory",
        },
        headers=_headers(created, "dup"),
    )
    assert response.status_code == 400
    assert "meterCode" in response.json()["error"]["details"]["fields"]


def test_parent_cycle_is_rejected(fems):
    client, created = fems
    upper = _create(client, created, "upper", meterCode="M-UP")
    lower = _create(
        client, created, "lower", meterCode="M-LOW", parentMeterId=upper["id"]
    )
    response = client.patch(
        f"{BASE}/{upper['id']}",
        json={"parentMeterId": lower["id"]},
        headers=_headers(created, "cycle"),
    )
    assert response.status_code == 400
    assert "parentMeterId" in response.json()["error"]["details"]["fields"]


def test_self_parent_is_rejected(fems):
    client, created = fems
    meter = _create(client, created, "self")
    response = client.patch(
        f"{BASE}/{meter['id']}",
        json={"parentMeterId": meter["id"]},
        headers=_headers(created, "self-parent"),
    )
    assert response.status_code == 400


def test_observed_meter_cannot_move(fems):
    client, created = fems
    inj = _meter(client, "M-INJ-01")
    response = client.patch(
        f"{BASE}/{inj['id']}",
        json={"parentMeterId": None},
        headers=_headers(created, "move"),
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["reason"] == "METER_IN_USE"
    assert details["fields"] == ["parentMeterId"]
    assert {r["table"] for r in details["references"]} == {
        "fems.energy_reading",
        "fems.energy_allocation",
    }


def test_observed_meter_can_be_renamed(fems):
    client, created = fems
    inj = _meter(client, "M-INJ-01")
    response = client.patch(
        f"{BASE}/{inj['id']}",
        json={"name": "사출 1호 전력량계"},
        headers=_headers(created, "rename"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "사출 1호 전력량계"


def test_unobserved_meter_can_move(fems):
    client, created = fems
    meter = _create(client, created, "fresh")
    response = client.patch(
        f"{BASE}/{meter['id']}",
        json={
            "locationId": _location(client, "L-INJ"),
            "equipmentId": _equipment(client, "INJ-02"),
        },
        headers=_headers(created, "fresh-move"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["equipmentId"] == _equipment(client, "INJ-02")


def test_meter_with_children_cannot_be_deleted(fems):
    client, created = fems
    main = _meter(client, "M-MAIN")
    response = client.delete(
        f"{BASE}/{main['id']}", headers=_headers(created, "del-main")
    )
    assert response.status_code == 409
    labels = {r["label"] for r in response.json()["error"]["details"]["references"]}
    assert labels == {"하위 계측기", "계측 채널"}


def test_empty_meter_can_be_deleted(fems):
    client, created = fems
    meter = _create(client, created, "to-delete")
    response = client.delete(f"{BASE}/{meter['id']}", headers=_headers(created, "del"))
    assert response.status_code == 204
    assert client.get(f"{BASE}/{meter['id']}").status_code == 404


def test_create_meter_is_idempotent(fems):
    client, created = fems
    payload = {
        "meterCode": "M-IDEM",
        "name": "x",
        "locationId": _location(client, "L-UTL"),
        "scopeKind": "factory",
    }
    first = client.post(BASE, json=payload, headers=_headers(created, "same"))
    second = client.post(BASE, json=payload, headers=_headers(created, "same"))
    assert first.json() == second.json()
    assert len(client.get(BASE).json()["data"]) == 12


def test_create_meter_requires_csrf(fems):
    client, _ = fems
    response = client.post(BASE, json={}, headers={"Idempotency-Key": "k"})
    assert response.status_code in (400, 403)


def test_cumulative_channel_unit_must_match_source(fems):
    client, created = fems
    meter = _create(client, created, "m-unit")
    response = client.post(
        f"{BASE}/{meter['id']}/channels",
        json=_channel_payload(client, unit="MWh"),
        headers=_headers(created, "unit"),
    )
    assert response.status_code == 400
    assert "unit" in response.json()["error"]["details"]["fields"]


def test_instant_channel_may_use_other_unit(fems):
    client, created = fems
    meter = _create(client, created, "m-inst")
    response = client.post(
        f"{BASE}/{meter['id']}/channels",
        json=_channel_payload(client, measurementKind="INSTANT", unit="kW"),
        headers=_headers(created, "instant"),
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert (data["multiplier"], data["observed"]) == ("1.000000", False)
    assert _meter(client, "M-NEW")["channelCount"] == 1


def test_zero_multiplier_is_rejected(fems):
    client, created = fems
    meter = _create(client, created, "m-mult")
    response = client.post(
        f"{BASE}/{meter['id']}/channels",
        json=_channel_payload(client, multiplier="0"),
        headers=_headers(created, "mult"),
    )
    assert response.status_code == 400
    assert "multiplier" in response.json()["error"]["details"]["fields"]


def test_duplicate_channel_code_in_meter_is_rejected(fems):
    client, created = fems
    main = _meter(client, "M-MAIN")
    response = client.post(
        f"{BASE}/{main['id']}/channels",
        json=_channel_payload(client, channelCode="CH-MAIN-KWH"),
        headers=_headers(created, "dup-ch"),
    )
    assert response.status_code == 400
    assert "channelCode" in response.json()["error"]["details"]["fields"]


def test_channel_on_unknown_meter_is_not_found(fems):
    client, created = fems
    response = client.post(
        f"{BASE}/999999/channels",
        json=_channel_payload(client),
        headers=_headers(created, "no-meter"),
    )
    assert response.status_code == 404


def test_observed_channel_unit_cannot_change(fems):
    client, created = fems
    main = _meter(client, "M-MAIN")
    channel = main["channels"][0]
    response = client.patch(
        f"{BASE}/{main['id']}/channels/{channel['id']}",
        json={"measurementKind": "INSTANT", "unit": "kW"},
        headers=_headers(created, "ch-unit"),
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["reason"] == "CHANNEL_IN_USE"
    assert details["fields"] == ["measurementKind", "unit"]


def test_observed_channel_can_be_deactivated(fems):
    client, created = fems
    main = _meter(client, "M-MAIN")
    channel = main["channels"][0]
    response = client.patch(
        f"{BASE}/{main['id']}/channels/{channel['id']}",
        json={"isActive": False},
        headers=_headers(created, "ch-off"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["isActive"] is False


def test_observed_channel_cannot_be_deleted(fems):
    client, created = fems
    main = _meter(client, "M-MAIN")
    channel = main["channels"][0]
    response = client.delete(
        f"{BASE}/{main['id']}/channels/{channel['id']}",
        headers=_headers(created, "ch-del"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REFERENCED_BY_OTHERS"


def test_fresh_channel_can_be_deleted(fems):
    client, created = fems
    meter = _create(client, created, "m-del-ch")
    channel = client.post(
        f"{BASE}/{meter['id']}/channels",
        json=_channel_payload(client),
        headers=_headers(created, "ch-new"),
    ).json()["data"]
    response = client.delete(
        f"{BASE}/{meter['id']}/channels/{channel['id']}",
        headers=_headers(created, "ch-del-fresh"),
    )
    assert response.status_code == 204
    assert _meter(client, "M-NEW")["channelCount"] == 0


def test_disabled_module_blocks_meters(fems):
    client, created = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off"),
    )
    response = client.get(BASE)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"
