"""FEMS-1g: 비용 배분(F43)·고지서 대조(F42)·설비 부서(F06)·신재생 발전(F37) — DSN-15 Q4.

비용은 **그 달 청구 총액을 설비 배분량 비율로** 나눈다. 설비에 배분되지 않은 공용 비용은 설비에
떠넘기지 않고 따로 돌려준다. 확정한 비용 배분만 ERP가 참고로 읽는다.
"""

from datetime import timedelta
from decimal import Decimal
from itertools import count

import pytest
from fs.common.auth import AuthContext
from fs.fems import interface as fems
from sqlalchemy import text

F = "/api/v1/fems"
_keys = count()


@pytest.fixture
def space(guest_space):
    return guest_space


def _h(created):
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": f"cs{next(_keys)}",
    }


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _month(client) -> str:
    return _ok(client.get(f"{F}/billing"))["period"]["to"]


def _site_total(client, month) -> Decimal:
    return Decimal(_ok(client.get(f"{F}/billing?from={month}&to={month}"))["total"])


def _run(client, created, month):
    return client.post(f"{F}/cost-runs", json={"month": month}, headers=_h(created))


def _context(created) -> AuthContext:
    return AuthContext(
        actor_kind="GUEST",
        actor_key="test",
        workspace_id=created["workspaceId"],
        generation_id=created["generationId"],
        user_id=None,
        roles=("GUEST",),
        token=None,
    )


# ---------- 비용 배분 (F-22) ----------


def test_lines_plus_unallocated_make_the_site_total(space):
    """설비 줄의 합 + 공용 비용 = 그 달 청구 총액. 어디서도 새거나 부풀지 않는다."""
    client, created, _ = space
    month = _month(client)
    run = _ok(_run(client, created, month), 201)
    assert run["status"] == "draft" and run["lines"]
    lines = sum(Decimal(line["cost"]) for line in run["lines"])
    assert Decimal(run["total"]) == lines
    assert abs(
        lines + Decimal(run["unallocatedCost"]) - _site_total(client, month)
    ) < Decimal("0.05")
    assert Decimal(run["unallocatedCost"]) >= 0


def test_equipment_cost_never_exceeds_the_bill(space):
    client, created, _ = space
    month = _month(client)
    run = _ok(_run(client, created, month), 201)
    assert Decimal(run["total"]) <= _site_total(client, month) + Decimal("0.05")


def test_lines_carry_department_and_main_item_snapshots(space):
    client, created, _ = space
    month = _month(client)
    departments = _ok(client.get(f"{F}/lookups/departments"))
    assert departments["hrEnabled"] and departments["rows"]
    code = departments["rows"][0]["code"]
    equipments = _ok(client.get(f"{F}/equipments"))
    target = next(e for e in equipments if e["equipmentCode"])
    _ok(
        client.patch(
            f"{F}/equipments/{target['id']}",
            json={"departmentCode": code},
            headers=_h(created),
        )
    )
    run = _ok(_run(client, created, month), 201)
    mine = [ln for ln in run["lines"] if ln["equipmentCode"] == target["equipmentCode"]]
    if mine:  # 그 설비에 배분이 있을 때만 부서가 붙는다
        assert all(ln["departmentCode"] == code for ln in mine)
    groups = {g["departmentCode"] for g in run["byDepartment"]}
    assert "미지정" in groups or groups == {code}


def test_missing_tariff_blocks_the_run(space):
    """요금제가 빠지면 총액이 부분 합계다. 배분하지 않는다."""
    client, created, engine = space
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM fems.tariff WHERE workspace_id=:w AND generation_id=:g"),
            {"w": created["workspaceId"], "g": created["generationId"]},
        )
    response = _run(client, created, _month(client))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "INCOMPLETE"


def test_run_without_readings_is_refused(space):
    client, created, _ = space
    response = _run(client, created, "1999-01")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "NO_READINGS"


def test_confirm_then_new_version_supersedes(space):
    client, created, _ = space
    month = _month(client)
    first = _ok(_run(client, created, month), 201)
    confirmed = _ok(
        client.post(f"{F}/cost-runs/{first['id']}/confirm", headers=_h(created))
    )
    assert confirmed["status"] == "confirmed"
    assert (
        client.post(
            f"{F}/cost-runs/{first['id']}/confirm", headers=_h(created)
        ).status_code
        == 409
    )
    second = _ok(_run(client, created, month), 201)
    assert second["version"] == 2
    _ok(client.post(f"{F}/cost-runs/{second['id']}/confirm", headers=_h(created)))
    states = {
        r["version"]: r["status"]
        for r in _ok(client.get(f"{F}/cost-runs"))
        if r["costMonth"] == month
    }
    assert states == {1: "superseded", 2: "confirmed"}


def test_erp_reads_only_the_confirmed_run(space):
    """초안은 ERP에 보이지 않는다. 확정해야 읽힌다. FEMS를 끄면 None이다."""
    client, created, engine = space
    month = _month(client)
    context = _context(created)
    run = _ok(_run(client, created, month), 201)
    with engine.begin() as c:
        assert fems.energy_costs(c, context, month) == []
    _ok(client.post(f"{F}/cost-runs/{run['id']}/confirm", headers=_h(created)))
    with engine.begin() as c:
        rows = fems.energy_costs(c, context, month)
        assert rows and {"equipmentCode", "departmentCode", "itemCode", "cost"} <= set(
            rows[0]
        )
        assert sum(Decimal(r["cost"]) for r in rows) == Decimal(run["total"])
        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false "
                "WHERE workspace_id=:w AND module_key='fems'"
            ),
            {"w": created["workspaceId"]},
        )
        assert fems.energy_costs(c, context, month) is None


# ---------- 고지서 대조 (F-23) ----------


def _billable(client) -> dict:
    return next(
        s for s in _ok(client.get(f"{F}/energy-sources")) if s["sourceCode"] == "ELEC"
    )


def _bill(client, created, month, **extra):
    body = {
        "energySourceId": _billable(client)["id"],
        "billMonth": month,
        "billedQty": "1000",
        "billedAmount": "1",
        **extra,
    }
    return client.post(f"{F}/utility-bills", json=body, headers=_h(created))


def _calculated(client, month) -> str:
    sources = _ok(client.get(f"{F}/billing?from={month}&to={month}"))["sources"]
    return next(s for s in sources if s["sourceCode"] == "ELEC")["total"]


def test_matching_bill_needs_no_reason(space):
    client, created, _ = space
    month = _month(client)
    calculated = Decimal(_calculated(client, month)).quantize(Decimal("0.01"))
    bill = _ok(_bill(client, created, month, billedAmount=str(calculated)), 201)
    assert Decimal(bill["difference"]) == 0
    assert Decimal(bill["calculatedAmount"]) == calculated


def test_difference_needs_a_reason(space):
    """사유 없는 차이는 나중에 아무도 설명할 수 없다."""
    client, created, _ = space
    month = _month(client)
    response = _bill(client, created, month, billedAmount="1")
    assert response.status_code == 400
    assert "note" in response.json()["error"]["details"]["fields"]
    ok = _bill(
        client, created, month, billedAmount="1", note="검침일 차이로 청구 기간이 다름"
    )
    bill = _ok(ok, 201)
    assert Decimal(bill["difference"]) < 0
    assert bill["differenceRate"] is not None


def test_bill_for_the_same_month_is_unique_until_deleted(space):
    client, created, _ = space
    month = _month(client)
    amount = str(Decimal(_calculated(client, month)).quantize(Decimal("0.01")))
    first = _ok(_bill(client, created, month, billedAmount=amount), 201)
    assert _bill(client, created, month, billedAmount=amount).status_code == 409
    _ok(client.delete(f"{F}/utility-bills/{first['id']}", headers=_h(created)))
    _ok(_bill(client, created, month, billedAmount=amount), 201)


def test_non_billable_source_has_no_bill(space):
    """요금 부과 대상이 아닌 에너지원은 고지서가 없다. 시드에 그런 에너지원이 없어 직접 만든다."""
    client, created, _ = space
    month = _month(client)
    sources = _ok(client.get(f"{F}/billing?from={month}&to={month}"))["sources"]
    other = next(s for s in sources if s["sourceCode"] != "ELEC")
    _ok(
        client.patch(
            f"{F}/energy-sources/{other['energySourceId']}",
            json={"isBillable": False},
            headers=_h(created),
        )
    )
    response = client.post(
        f"{F}/utility-bills",
        json={
            "energySourceId": other["energySourceId"],
            "billMonth": month,
            "billedQty": "1",
            "billedAmount": "1",
            "note": "사유",
        },
        headers=_h(created),
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "NOT_BILLABLE"


# ---------- 설비 부서 (F-10) ----------


def test_department_must_exist_in_hr(space):
    client, created, _ = space
    target = _ok(client.get(f"{F}/equipments"))[0]
    response = client.patch(
        f"{F}/equipments/{target['id']}",
        json={"departmentCode": "NO-SUCH-DEPT"},
        headers=_h(created),
    )
    assert response.status_code == 400
    assert "departmentCode" in response.json()["error"]["details"]["fields"]


def test_department_can_be_assigned_and_cleared(space):
    client, created, _ = space
    code = _ok(client.get(f"{F}/lookups/departments"))["rows"][0]["code"]
    target = _ok(client.get(f"{F}/equipments"))[0]
    set_ = _ok(
        client.patch(
            f"{F}/equipments/{target['id']}",
            json={"departmentCode": code},
            headers=_h(created),
        )
    )
    assert set_["departmentCode"] == code
    cleared = _ok(
        client.patch(
            f"{F}/equipments/{target['id']}",
            json={"departmentCode": None},
            headers=_h(created),
        )
    )
    assert cleared["departmentCode"] is None


def test_name_still_cannot_be_nulled(space):
    """부서 코드만 비울 수 있다. 필수 항목을 null로 비우는 것은 여전히 막는다."""
    client, created, _ = space
    target = _ok(client.get(f"{F}/equipments"))[0]
    response = client.patch(
        f"{F}/equipments/{target['id']}", json={"name": None}, headers=_h(created)
    )
    assert response.status_code == 400


def test_lookup_says_when_hr_is_off(space):
    client, created, engine = space
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false "
                "WHERE workspace_id=:w AND module_key='hr'"
            ),
            {"w": created["workspaceId"]},
        )
    data = _ok(client.get(f"{F}/lookups/departments"))
    assert data["hrEnabled"] is False and data["rows"] == []


# ---------- 신재생 발전 (F-11) ----------


def _generation_setup(client, created) -> int:
    """발전 에너지원 + 발전 계측기·채널을 만들고 채널 id를 돌려준다."""
    source = _ok(
        client.post(
            f"{F}/energy-sources",
            json={
                "sourceCode": "SOLAR",
                "name": "태양광",
                "sourceKind": "GENERATION",
                "measureUnit": "kWh",
                "isBillable": False,
            },
            headers=_h(created),
        ),
        201,
    )
    location = _ok(client.get(f"{F}/locations"))[0]
    meter = _ok(
        client.post(
            f"{F}/meters",
            json={
                "meterCode": "MT-SOLAR",
                "name": "태양광 인버터",
                "locationId": location["id"],
                "scopeKind": "generation",
            },
            headers=_h(created),
        ),
        201,
    )
    channel = _ok(
        client.post(
            f"{F}/meters/{meter['id']}/channels",
            json={
                "channelCode": "CH-SOLAR",
                "name": "발전량",
                "energySourceId": source["id"],
                "measurementKind": "INSTANT",
                "unit": "kWh",
            },
            headers=_h(created),
        ),
        201,
    )
    return channel["id"]


def test_generation_source_cannot_be_billable(space):
    """발전은 만든 양이라 요금을 내지 않는다. 부과 대상으로 두면 요금제 없다며 요금을 막는다."""
    client, created, _ = space
    response = client.post(
        f"{F}/energy-sources",
        json={
            "sourceCode": "SOLAR",
            "name": "태양광",
            "sourceKind": "GENERATION",
            "measureUnit": "kWh",
            "isBillable": True,
        },
        headers=_h(created),
    )
    assert response.status_code == 400
    assert "isBillable" in response.json()["error"]["details"]["fields"]


def test_generation_is_not_counted_as_consumption(space):
    """발전량이 소비량·요금·피크에 섞이면 안 된다 — 그것이 이 단계의 가장 큰 위험이다."""
    client, created, engine = space
    month = _month(client)
    before = _ok(client.get(f"{F}/dashboard?month={month}"))
    total_before = _site_total(client, month)
    channel_id = _generation_setup(client, created)
    with engine.begin() as c:
        latest = c.execute(
            text(
                "SELECT max(period_start) FROM fems.energy_reading "
                "WHERE workspace_id=:w AND generation_id=:g"
            ),
            {"w": created["workspaceId"], "g": created["generationId"]},
        ).scalar_one()
    for hour in range(1, 4):
        _ok(
            client.post(
                f"{F}/readings",
                json={
                    "channelId": channel_id,
                    "periodStart": (latest + timedelta(hours=hour)).isoformat(),
                    "value": "500",
                },
                headers=_h(created),
            ),
            201,
        )
    after = _ok(client.get(f"{F}/dashboard?month={month}"))
    # 소비 쪽은 그대로다.
    assert after["primaryEnergy"]["total"] == before["primaryEnergy"]["total"]
    assert after["peak"] == before["peak"]
    assert _site_total(client, month) == total_before, "발전량이 요금에 섞였다"
    # 발전은 따로 센다.
    solar = next(g for g in after["generation"] if g["sourceCode"] == "SOLAR")
    assert Decimal(solar["quantity"]) == Decimal(1500)
