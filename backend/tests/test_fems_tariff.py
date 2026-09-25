"""FS-018 F-14 요금제 API. 검증 항목마다 테스트를 나눈다."""

import pytest
from fastapi.testclient import TestClient
from fs.main import create_app
from sqlalchemy import Engine

BASE = "/api/v1/fems/tariffs"
SOURCES = "/api/v1/fems/energy-sources"


@pytest.fixture
def fems(guest_space):
    return guest_space


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _source_id_by_code(client, code: str) -> int:
    rows = client.get(SOURCES).json()["data"]
    return next(r["id"] for r in rows if r["sourceCode"] == code)


def _other_guest(engine: Engine):
    with TestClient(create_app(), base_url="https://testserver") as other:
        created = other.post(
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "other-guest"}
        ).json()["data"]
        return other, created


def test_list_returns_seed_tariffs(fems):
    client, _, _ = fems
    body = client.get(BASE).json()
    assert len(body["data"]) == 4
    assert body["page"] == {"offset": 0, "limit": 50, "total": 4}
    codes = [r["tariffCode"] for r in body["data"]]
    assert "TR-ELEC-01" in codes
    assert "TR-ELEC-02" in codes
    assert "TR-GAS-01" in codes
    assert "TR-WTR-01" in codes


def test_seed_electricity_tariffs_do_not_overlap(fems):
    # 시드 전력 요금제 두 건(2025-09~2026-08, 2026-09~계속)은 겹치지 않는다
    client, _, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    rows = client.get(BASE, params={"energySourceId": elec_id}).json()["data"]
    assert len(rows) == 2
    tr1 = next(r for r in rows if r["tariffCode"] == "TR-ELEC-01")
    tr2 = next(r for r in rows if r["tariffCode"] == "TR-ELEC-02")
    assert tr1["effectiveFrom"] == "2025-09"
    assert tr1["effectiveTo"] == "2026-08"
    assert tr2["effectiveFrom"] == "2026-09"
    assert tr2["effectiveTo"] is None


def test_filter_by_energy_source_id(fems):
    client, _, _ = fems
    gas_id = _source_id_by_code(client, "GAS")
    rows = client.get(BASE, params={"energySourceId": gas_id}).json()["data"]
    assert len(rows) == 1
    assert rows[0]["tariffCode"] == "TR-GAS-01"


def test_get_single_tariff(fems):
    client, _, _ = fems
    tariffs = client.get(BASE).json()["data"]
    target = tariffs[0]
    single = client.get(f"{BASE}/{target['id']}").json()["data"]
    assert single["id"] == target["id"]
    assert single["tariffCode"] == target["tariffCode"]
    assert isinstance(single["basicCharge"], str)
    assert isinstance(single["usageRate"], str)


def test_create_tariff_period_overlap_rejected(fems):
    # 겹치는 기간 등록은 409
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    # TR-ELEC-01은 2025-09 ~ 2026-08 적용 중.
    # 2026-01 ~ 2026-12 등록 시 겹침 발생
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-ELEC-OVERLAP",
        "name": "겹치는 요금제",
        "basicCharge": "200000",
        "usageRate": "110",
        "effectiveFrom": "2026-01",
        "effectiveTo": "2026-12",
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "overlap"))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "PRECONDITION_NOT_MET"
    assert error["details"]["reason"] == "PERIOD_OVERLAP"
    conflict_codes = [c["tariffCode"] for c in error["details"]["conflicts"]]
    assert "TR-ELEC-01" in conflict_codes


def test_create_tariff_adjacent_period_allowed(fems):
    # 붙어 있는 기간(끝난 다음 달부터 시작)은 허용
    client, created, _ = fems
    # TR-ELEC-01(2025-09 ~ 2026-08) 이전 구간으로 2025-01 ~ 2025-08 등록 (2025-08 바로 다음 달이 2025-09)
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-ELEC-PREV",
        "name": "이전 요금제",
        "basicCharge": "240000",
        "usageRate": "115",
        "effectiveFrom": "2025-01",
        "effectiveTo": "2025-08",
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "adjacent"))
    assert response.status_code == 201
    assert response.json()["data"]["tariffCode"] == "TR-ELEC-PREV"


def test_create_tariff_both_infinite_overlap(fems):
    # 계속 적용(null)끼리는 겹침
    client, created, _ = fems
    # TR-ELEC-02는 2026-09 ~ None 적용 중.
    # 또 다른 2027-01 ~ None 등록 시 둘 다 계속 적용이므로 겹침
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-ELEC-INF",
        "name": "무한 요금제",
        "basicCharge": "260000",
        "usageRate": "135",
        "effectiveFrom": "2027-01",
        "effectiveTo": None,
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "inf-overlap"))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "PERIOD_OVERLAP"


def test_create_tariff_different_energy_source_period_overlap_allowed(fems):
    # 다른 에너지원이면 기간이 겹쳐도 허용
    client, created, _ = fems
    gas_id = _source_id_by_code(client, "GAS")
    # GAS의 TR-GAS-01은 2025-09 ~ None.
    # ELEC의 2025-09 ~ None과 동일한 기간이어도 에너지원이 다르므로 허용
    payload = {
        "energySourceId": gas_id,
        "tariffCode": "TR-GAS-NEW",
        "name": "새 가스 요금제 (이전 구간)",
        "basicCharge": "28000",
        "usageRate": "1050",
        "effectiveFrom": "2024-01",
        "effectiveTo": "2025-08",
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "diff-source"))
    assert response.status_code == 201


def test_update_tariff_self_does_not_overlap(fems):
    # 자기 자신을 수정할 때는 자기와의 겹침으로 보지 않는다
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    rows = client.get(BASE, params={"energySourceId": elec_id}).json()["data"]
    tr1 = next(r for r in rows if r["tariffCode"] == "TR-ELEC-01")
    # TR-ELEC-01의 이름과 단가만 수정, 기간은 동일
    response = client.patch(
        f"{BASE}/{tr1['id']}",
        json={"name": "이름 변경 요금제", "usageRate": "125"},
        headers=_headers(created, "patch-self"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "이름 변경 요금제"
    assert response.json()["data"]["usageRate"] == "125.0000"


def test_update_tariff_period_overlap_rejected(fems):
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    rows = client.get(BASE, params={"energySourceId": elec_id}).json()["data"]
    tr1 = next(r for r in rows if r["tariffCode"] == "TR-ELEC-01")
    # TR-ELEC-01의 종료일을 2026-10으로 늘리면 TR-ELEC-02(2026-09~)와 겹침
    response = client.patch(
        f"{BASE}/{tr1['id']}",
        json={"effectiveTo": "2026-10"},
        headers=_headers(created, "patch-overlap"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "PERIOD_OVERLAP"


def test_create_tariff_rejects_foreign_energy_source_id(fems):
    # 다른 공간의 energy_source_id는 400
    client, created, engine = fems
    other, _ = _other_guest(engine)
    foreign_source_id = other.get(SOURCES).json()["data"][0]["id"]
    payload = {
        "energySourceId": foreign_source_id,
        "tariffCode": "TR-FOREIGN",
        "name": "타 공간 에너지원 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2026-01",
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "foreign-src"))
    assert response.status_code == 400
    assert "energySourceId" in response.json()["error"]["details"]["fields"]


def test_create_tariff_effective_to_before_from_rejected(fems):
    # effective_to가 있으면 effective_from 이상이어야 한다. 아니면 400 fields.effectiveTo
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-INVALID-RANGE",
        "name": "역순 기간 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2026-05",
        "effectiveTo": "2026-04",
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "rev-range"))
    assert response.status_code == 400
    assert "effectiveTo" in response.json()["error"]["details"]["fields"]


def test_update_tariff_effective_to_before_from_rejected(fems):
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    rows = client.get(BASE, params={"energySourceId": elec_id}).json()["data"]
    tr1 = next(r for r in rows if r["tariffCode"] == "TR-ELEC-01")
    response = client.patch(
        f"{BASE}/{tr1['id']}",
        json={"effectiveTo": "2025-08"},  # effectiveFrom은 2025-09
        headers=_headers(created, "rev-range-patch"),
    )
    assert response.status_code == 400
    assert "effectiveTo" in response.json()["error"]["details"]["fields"]


def test_create_tariff_duplicate_code_rejected(fems):
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-ELEC-01",
        "name": "중복 코드 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2024-01",
        "effectiveTo": "2024-12",
    }
    response = client.post(BASE, json=payload, headers=_headers(created, "dup-code"))
    assert response.status_code == 400
    assert "tariffCode" in response.json()["error"]["details"]["fields"]


def test_create_tariff_idempotent_replay(fems):
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-REPLAY",
        "name": "재시도 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2024-01",
        "effectiveTo": "2024-12",
    }
    r1 = client.post(BASE, json=payload, headers=_headers(created, "rep-key"))
    assert r1.status_code == 201
    r2 = client.post(BASE, json=payload, headers=_headers(created, "rep-key"))
    assert r2.status_code == 201
    assert r1.json()["data"]["id"] == r2.json()["data"]["id"]


def test_update_tariff_set_effective_to_null(fems):
    # nullable 필드인 effectiveTo를 null로 수정
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    # 먼저 겹치지 않는 구간 2024-01 ~ 2024-12 요금제 생성
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-NULL-TEST",
        "name": "널 테스트 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2024-01",
        "effectiveTo": "2024-12",
    }
    t = client.post(BASE, json=payload, headers=_headers(created, "null-c")).json()[
        "data"
    ]
    # 2024-06으로 종료일 수정
    r1 = client.patch(
        f"{BASE}/{t['id']}",
        json={"effectiveTo": "2024-06"},
        headers=_headers(created, "null-u1"),
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["effectiveTo"] == "2024-06"


def test_delete_tariff_success_without_reference_check(fems):
    # 요금제는 참조하는 테이블이 없다. 삭제는 참조 검사 없이 가능하다.
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-DEL",
        "name": "삭제 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2024-01",
        "effectiveTo": "2024-12",
    }
    created_t = client.post(
        BASE, json=payload, headers=_headers(created, "del-c")
    ).json()["data"]
    del_res = client.delete(
        f"{BASE}/{created_t['id']}", headers=_headers(created, "del-1")
    )
    assert del_res.status_code == 204
    assert client.get(f"{BASE}/{created_t['id']}").status_code == 404


def test_delete_tariff_idempotent_replay(fems):
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-DEL-REP",
        "name": "삭제 재시도 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2024-01",
        "effectiveTo": "2024-12",
    }
    t = client.post(BASE, json=payload, headers=_headers(created, "del-rep-c")).json()[
        "data"
    ]
    assert (
        client.delete(
            f"{BASE}/{t['id']}", headers=_headers(created, "del-rep")
        ).status_code
        == 204
    )
    assert (
        client.delete(
            f"{BASE}/{t['id']}", headers=_headers(created, "del-rep")
        ).status_code
        == 204
    )


def test_list_tariffs_sort_whitelist(fems):
    client, _, _ = fems
    assert client.get(BASE, params={"sort": "tariffCode:desc"}).status_code == 200
    assert client.get(BASE, params={"sort": "invalid:desc"}).status_code == 400


def test_disabled_module_blocks_tariff_reads(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off"),
    )
    response = client.get(BASE)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"


def test_disabled_module_blocks_tariff_writes(fems):
    client, created, _ = fems
    elec_id = _source_id_by_code(client, "ELEC")
    payload = {
        "energySourceId": elec_id,
        "tariffCode": "TR-BLOCKED",
        "name": "차단 요금제",
        "basicCharge": "100000",
        "usageRate": "100",
        "effectiveFrom": "2024-01",
    }
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_headers(created, "fems-off-2"),
    )
    response = client.post(BASE, json=payload, headers=_headers(created, "blocked"))
    assert response.status_code == 409
