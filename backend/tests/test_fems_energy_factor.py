"""FS-018k F-13 환산·배출계수 API. 검증 항목마다 테스트를 나눈다."""

import pytest

BASE = "/api/v1/fems/energy-factors"
SOURCES = "/api/v1/fems/energy-sources"


@pytest.fixture
def fems(guest_space):
    return guest_space[:2]


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _source_id(client, code: str) -> int:
    rows = client.get(SOURCES).json()["data"]
    return next(r["id"] for r in rows if r["sourceCode"] == code)


def _find(client, code: str, kind: str, year: str) -> dict:
    source = _source_id(client, code)
    rows = client.get(
        BASE, params={"factorKind": kind, "energySourceId": source}
    ).json()["data"]
    return next(r for r in rows if r["effectiveYear"] == year)


def _new(client, **override) -> dict:
    return {
        "energySourceId": _source_id(client, "ELEC"),
        "factorKind": "EMISSION",
        "effectiveYear": "2027",
        "factorValue": "0.000455",
        "sourceNote": "합성 예시값",
        **override,
    }


def test_list_returns_seed_factors(fems):
    client, _ = fems
    body = client.get(BASE).json()
    # ELEC·GAS × PRIMARY·EMISSION × 2025·2026. 용수는 계수가 없다.
    assert body["page"]["total"] == 8
    assert body["data"][0]["effectiveYear"] == "2026"


def test_kind_filter_separates_tabs(fems):
    client, _ = fems
    rows = client.get(BASE, params={"factorKind": "PRIMARY"}).json()["data"]
    assert len(rows) == 4
    assert {r["factorKind"] for r in rows} == {"PRIMARY"}
    assert {r["factorUnit"] for r in rows} == {"TOE/kWh", "TOE/Nm3"}


def test_values_are_strings(fems):
    client, _ = fems
    row = _find(client, "ELEC", "EMISSION", "2026")
    single = client.get(f"{BASE}/{row['id']}").json()["data"]
    assert single["factorValue"] == "0.000460"
    assert single["factorUnit"] == "tCO2eq/kWh"


def test_create_derives_unit_from_kind_and_source(fems):
    client, created = fems
    gas = _source_id(client, "GAS")
    response = client.post(
        BASE,
        json=_new(client, energySourceId=gas, factorKind="PRIMARY"),
        headers=_headers(created, "create-gas"),
    )
    assert response.status_code == 201
    assert response.json()["data"]["factorUnit"] == "TOE/Nm3"


def test_unit_is_not_accepted_from_client(fems):
    client, created = fems
    response = client.post(
        BASE,
        json=_new(client, factorUnit="TOE/kWh"),
        headers=_headers(created, "unit"),
    )
    assert response.status_code == 400


def test_duplicate_year_is_rejected(fems):
    client, created = fems
    response = client.post(
        BASE, json=_new(client, effectiveYear="2026"), headers=_headers(created, "dup")
    )
    assert response.status_code == 400
    assert "effectiveYear" in response.json()["error"]["details"]["fields"]


def test_same_year_other_kind_is_allowed(fems):
    # 같은 에너지원·연도라도 유형이 다르면 별개 계수다.
    client, created = fems
    client.delete(
        f"{BASE}/{_find(client, 'ELEC', 'PRIMARY', '2026')['id']}",
        headers=_headers(created, "drop-primary"),
    )
    response = client.post(
        BASE,
        json=_new(client, factorKind="PRIMARY", effectiveYear="2026"),
        headers=_headers(created, "primary-2026"),
    )
    assert response.status_code == 201


def test_zero_value_is_rejected(fems):
    client, created = fems
    response = client.post(
        BASE, json=_new(client, factorValue="0"), headers=_headers(created, "zero")
    )
    assert response.status_code == 400
    assert "factorValue" in response.json()["error"]["details"]["fields"]


def test_seven_decimals_are_rejected(fems):
    client, created = fems
    response = client.post(
        BASE,
        json=_new(client, factorValue="0.0000001"),
        headers=_headers(created, "decimals"),
    )
    assert response.status_code == 400


def test_year_format_is_validated(fems):
    client, created = fems
    response = client.post(
        BASE, json=_new(client, effectiveYear="27"), headers=_headers(created, "year")
    )
    assert response.status_code == 400


def test_utility_source_is_rejected(fems):
    client, created = fems
    water = _source_id(client, "WATER")
    response = client.post(
        BASE, json=_new(client, energySourceId=water), headers=_headers(created, "wtr")
    )
    assert response.status_code == 400
    assert "energySourceId" in response.json()["error"]["details"]["fields"]


def test_other_space_source_is_rejected(fems):
    client, created = fems
    response = client.post(
        BASE,
        json=_new(client, energySourceId=999999),
        headers=_headers(created, "foreign"),
    )
    assert response.status_code == 400


def test_create_is_idempotent(fems):
    client, created = fems
    payload = _new(client)
    first = client.post(BASE, json=payload, headers=_headers(created, "same"))
    second = client.post(BASE, json=payload, headers=_headers(created, "same"))
    assert first.json() == second.json()
    assert client.get(BASE).json()["page"]["total"] == 9


def test_create_requires_csrf(fems):
    client, _ = fems
    response = client.post(BASE, json=_new(client), headers={"Idempotency-Key": "k"})
    assert response.status_code == 403


def test_update_value_and_note(fems):
    client, created = fems
    row = _find(client, "GAS", "EMISSION", "2026")
    response = client.patch(
        f"{BASE}/{row['id']}",
        json={"factorValue": "0.002300", "sourceNote": "개정"},
        headers=_headers(created, "patch"),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["factorValue"], data["sourceNote"]) == ("0.002300", "개정")


def test_update_cannot_change_kind_or_source(fems):
    client, created = fems
    row = _find(client, "GAS", "EMISSION", "2026")
    response = client.patch(
        f"{BASE}/{row['id']}",
        json={"factorKind": "PRIMARY"},
        headers=_headers(created, "kind"),
    )
    assert response.status_code == 400


def test_update_to_existing_year_is_rejected(fems):
    client, created = fems
    row = _find(client, "GAS", "EMISSION", "2026")
    response = client.patch(
        f"{BASE}/{row['id']}",
        json={"effectiveYear": "2025"},
        headers=_headers(created, "year-dup"),
    )
    assert response.status_code == 400


def test_update_null_is_rejected(fems):
    client, created = fems
    row = _find(client, "GAS", "EMISSION", "2026")
    response = client.patch(
        f"{BASE}/{row['id']}",
        json={"sourceNote": None},
        headers=_headers(created, "null"),
    )
    assert response.status_code == 400


def test_delete_then_not_found(fems):
    client, created = fems
    row = _find(client, "GAS", "PRIMARY", "2025")
    response = client.delete(f"{BASE}/{row['id']}", headers=_headers(created, "del"))
    assert response.status_code == 204
    assert client.get(f"{BASE}/{row['id']}").status_code == 404


def test_recreated_factor_is_used_by_emissions(fems):
    # 서버가 정한 단위가 채널 단위와 맞아 배출량 계산에 그대로 쓰인다.
    client, created = fems
    row = _find(client, "GAS", "EMISSION", "2026")
    client.delete(f"{BASE}/{row['id']}", headers=_headers(created, "drop"))
    gas = _source_id(client, "GAS")
    client.post(
        BASE,
        json=_new(client, energySourceId=gas, effectiveYear="2026", factorValue="1"),
        headers=_headers(created, "recreate"),
    )
    period = {"from": "2026-09-01", "to": "2026-09-24"}
    data = client.get("/api/v1/fems/emissions", params=period).json()["data"]
    source = next(s for s in data["sources"] if s["sourceCode"] == "GAS")
    assert source["status"] == "CALCULATED"
    assert source["emission"] == source["consumption"]["quantity"]


def test_disabled_module_blocks_factors(fems):
    client, created = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off"),
    )
    response = client.get(BASE)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"
