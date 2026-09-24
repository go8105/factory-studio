"""FS-018i F-05 생산량 등록 API. 검증 항목마다 테스트를 나눈다.

시드: 확정 27행, 원천 키 26개(MES:LT-0016:INS는 v1·v2 모두 확정), MES:LT-0018:INS는 생산량 0.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine

BASE = "/api/v1/fems/production-records"


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
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "production"}
        ).json()["data"]
        yield client, created
    reset_engine()


def _h(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _equipment(client, code: str) -> int:
    rows = client.get("/api/v1/fems/equipments", params={"limit": 200}).json()["data"]
    return next(r["id"] for r in rows if r["equipmentCode"] == code)


def _body(client, **over):
    return {
        "equipmentId": _equipment(client, "INS-01"),
        "itemCode": "FG-C100",
        "startDate": "2026-09-20",
        "endDate": "2026-09-21",
        "productionQty": "120.5",
        "unit": "EA",
        **over,
    }


def _create(client, created, key="c", **over):
    return client.post(BASE, json=_body(client, **over), headers=_h(created, key))


def _confirmed(client, created, key="c", **over):
    record = _create(client, created, key, **over).json()["data"]
    return client.post(
        f"{BASE}/{record['id']}/confirm", headers=_h(created, key + "-f")
    ).json()["data"]


def _seed(client, source_key: str, history=False):
    rows = client.get(
        BASE, params={"includeHistory": str(history).lower(), "limit": 200}
    ).json()["data"]
    return [r for r in rows if r["sourceKey"] == source_key]


def test_list_shows_latest_version_per_source(fems):
    client, _ = fems
    assert client.get(BASE).json()["page"]["total"] == 26
    assert [r["versionNo"] for r in _seed(client, "MES:LT-0016:INS")] == [2]


def test_history_shows_every_version(fems):
    client, _ = fems
    assert (
        client.get(BASE, params={"includeHistory": "true"}).json()["page"]["total"]
        == 27
    )


def test_only_latest_confirmed_version_is_effective(fems):
    client, _ = fems
    rows = _seed(client, "MES:LT-0016:INS", history=True)
    assert {r["versionNo"]: r["isEffective"] for r in rows} == {1: False, 2: True}


def test_zero_production_is_kept(fems):
    client, _ = fems
    assert _seed(client, "MES:LT-0018:INS")[0]["productionQty"] == "0.000"


def test_create_makes_draft_version_one(fems):
    client, created = fems
    record = _create(client, created).json()["data"]
    assert (record["status"], record["versionNo"], record["sourceKey"]) == (
        "draft",
        1,
        "MAN-20260920-001",
    )


def test_create_converts_dates_to_site_day_boundaries(fems):
    client, created = fems
    record = _create(client, created).json()["data"]
    assert (record["periodStart"], record["periodEnd"]) == (
        "2026-09-19T15:00:00+00:00",
        "2026-09-21T15:00:00+00:00",
    )
    assert (record["startDate"], record["endDate"]) == ("2026-09-20", "2026-09-21")


def test_manual_source_key_sequence_increments(fems):
    client, created = fems
    _create(client, created, "a")
    second = _create(client, created, "b", itemCode="FG-C200").json()["data"]
    assert second["sourceKey"] == "MAN-20260920-002"


def test_create_replay_returns_same_record(fems):
    client, created = fems
    first = _create(client, created, "same").json()["data"]
    again = _create(client, created, "same").json()["data"]
    assert first["id"] == again["id"]


def test_create_requires_csrf(fems):
    client, _ = fems
    response = client.post(BASE, json=_body(client), headers={"Idempotency-Key": "x"})
    assert response.status_code == 403


def test_end_before_start_is_rejected(fems):
    client, created = fems
    response = _create(client, created, startDate="2026-09-21", endDate="2026-09-20")
    assert "endDate" in response.json()["error"]["details"]["fields"]


def test_foreign_equipment_is_rejected(fems):
    client, created = fems
    response = _create(client, created, equipmentId=999999)
    assert "equipmentId" in response.json()["error"]["details"]["fields"]


def test_negative_quantity_is_rejected(fems):
    client, created = fems
    assert _create(client, created, productionQty="-1").status_code == 400


def test_quantity_over_three_decimals_is_rejected(fems):
    client, created = fems
    assert _create(client, created, productionQty="1.2345").status_code == 400


def test_draft_can_be_updated(fems):
    client, created = fems
    record = _create(client, created).json()["data"]
    updated = client.patch(
        f"{BASE}/{record['id']}", json={"productionQty": "99"}, headers=_h(created, "u")
    ).json()["data"]
    assert updated["productionQty"] == "99.000"


def test_confirmed_cannot_be_updated(fems):
    client, created = fems
    record = _confirmed(client, created)
    response = client.patch(
        f"{BASE}/{record['id']}", json={"productionQty": "1"}, headers=_h(created, "u")
    )
    assert (response.status_code, response.json()["error"]["code"]) == (
        409,
        "ALREADY_CONFIRMED",
    )


def test_draft_can_be_deleted(fems):
    client, created = fems
    record = _create(client, created).json()["data"]
    response = client.delete(f"{BASE}/{record['id']}", headers=_h(created, "d"))
    assert response.status_code == 204
    assert client.get(f"{BASE}/{record['id']}").status_code == 404


def test_confirmed_cannot_be_deleted(fems):
    client, created = fems
    record = _confirmed(client, created)
    response = client.delete(f"{BASE}/{record['id']}", headers=_h(created, "d"))
    assert response.status_code == 409


def test_confirm_sets_confirmed_at(fems):
    client, created = fems
    record = _confirmed(client, created)
    assert (record["status"], record["confirmedAt"] is not None) == ("confirmed", True)


def test_overlapping_confirmed_period_is_rejected(fems):
    client, created = fems
    first = _confirmed(client, created, "one")
    other = _create(
        client, created, "two", startDate="2026-09-21", endDate="2026-09-22"
    ).json()["data"]
    response = client.post(f"{BASE}/{other['id']}/confirm", headers=_h(created, "f"))
    details = response.json()["error"]["details"]
    assert details["reason"] == "PERIOD_OVERLAP"
    assert [c["sourceKey"] for c in details["conflicts"]] == [first["sourceKey"]]


def test_adjacent_period_is_allowed(fems):
    client, created = fems
    _confirmed(client, created, "one")
    record = _confirmed(
        client, created, "two", startDate="2026-09-22", endDate="2026-09-23"
    )
    assert record["status"] == "confirmed"


def test_other_item_on_same_equipment_may_overlap(fems):
    client, created = fems
    _confirmed(client, created, "one")
    record = _confirmed(client, created, "two", itemCode="FG-C200")
    assert record["status"] == "confirmed"


def test_revise_creates_next_draft_version(fems):
    client, created = fems
    record = _confirmed(client, created)
    revision = client.post(
        f"{BASE}/{record['id']}/revise", headers=_h(created, "r")
    ).json()["data"]
    assert (revision["sourceKey"], revision["versionNo"], revision["status"]) == (
        record["sourceKey"],
        2,
        "draft",
    )
    assert revision["productionQty"] == record["productionQty"]


def test_second_revision_while_draft_exists_is_rejected(fems):
    client, created = fems
    record = _confirmed(client, created)
    client.post(f"{BASE}/{record['id']}/revise", headers=_h(created, "r1"))
    response = client.post(f"{BASE}/{record['id']}/revise", headers=_h(created, "r2"))
    assert response.json()["error"]["details"]["reason"] == "DRAFT_EXISTS"


def test_revising_old_version_is_rejected(fems):
    client, created = fems
    old = _seed(client, "MES:LT-0016:INS", history=True)
    v1 = next(r for r in old if r["versionNo"] == 1)
    response = client.post(f"{BASE}/{v1['id']}/revise", headers=_h(created, "r"))
    assert response.json()["error"]["details"]["reason"] == "NOT_LATEST"


def test_revision_cannot_change_equipment(fems):
    client, created = fems
    record = _confirmed(client, created)
    revision = client.post(
        f"{BASE}/{record['id']}/revise", headers=_h(created, "r")
    ).json()["data"]
    response = client.patch(
        f"{BASE}/{revision['id']}",
        json={"equipmentId": _equipment(client, "INS-02")},
        headers=_h(created, "u"),
    )
    assert response.json()["error"]["details"]["reason"] == "REVISION_FIELDS_FIXED"


def test_confirmed_revision_becomes_effective(fems):
    client, created = fems
    record = _confirmed(client, created)
    revision = client.post(
        f"{BASE}/{record['id']}/revise", headers=_h(created, "r")
    ).json()["data"]
    client.patch(
        f"{BASE}/{revision['id']}",
        json={"productionQty": "130"},
        headers=_h(created, "u"),
    )
    client.post(f"{BASE}/{revision['id']}/confirm", headers=_h(created, "f"))
    rows = _seed(client, record["sourceKey"], history=True)
    assert {r["versionNo"]: r["isEffective"] for r in rows} == {1: False, 2: True}


def test_disabled_module_blocks_production(fems):
    client, created = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_h(created, "off"),
    )
    assert client.get(BASE).status_code == 409
