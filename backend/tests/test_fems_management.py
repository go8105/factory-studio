"""FEMS-1f: 절감 활동(F32)·월간 검토(F33)·온실가스 명세서(F35) — DSN-15 Q5·Q6.

확정한 검토·명세서는 바꾸지 않는다. 고치려면 새 초안을 만들고 확정하면 옛 확정본이 `superseded`가 된다.
초안은 기록이 아니라 작업 중인 계산이라 새 초안을 만들 때 지운다(CHECK가 draft만 confirmed_at 없음을 허용한다).
"""

from datetime import date, timedelta
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import text

F = "/api/v1/fems"
_keys = count()


@pytest.fixture
def space(guest_space):
    return guest_space


def _h(created):
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": f"mg{next(_keys)}",
    }


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _scope(created):
    return {"w": created["workspaceId"], "g": created["generationId"]}


def _elec_id(client) -> int:
    rows = client.get(f"{F}/energy-sources").json()["data"]
    return next(r["id"] for r in rows if r["sourceCode"] == "ELEC")


def _busy_equipment(engine, created) -> tuple[int, int]:
    """배분이 가장 많은 설비와 그 에너지원."""
    with engine.begin() as c:
        row = c.execute(
            text(
                "SELECT a.equipment_id, ch.energy_source_id "
                "FROM fems.energy_allocation a JOIN fems.meter_channel ch "
                " ON ch.workspace_id=a.workspace_id AND ch.generation_id=a.generation_id "
                " AND ch.id=a.meter_channel_id "
                "WHERE a.workspace_id=:w AND a.generation_id=:g AND a.equipment_id IS NOT NULL "
                "GROUP BY 1,2 ORDER BY count(*) DESC LIMIT 1"
            ),
            _scope(created),
        ).one()
    return row[0], row[1]


def _latest_day(client) -> date:
    return date.fromisoformat(_ok(client.get(f"{F}/billing"))["period"]["dateTo"])


def _saving_body(**extra) -> dict:
    return {
        "code": f"SV-{next(_keys)}",
        "title": "사출기 대기전력 차단",
        "energySourceId": 0,
        "expectedSaving": "1000",
        "investment": "500000",
        "baselineStartOn": "2026-08-25",
        "baselineEndOn": "2026-09-01",
        "startOn": "2026-09-01",
        **extra,
    }


def _create_saving(client, created, **extra) -> dict:
    body = _saving_body(**extra)
    if not body["energySourceId"]:
        body["energySourceId"] = _elec_id(client)
    return _ok(client.post(f"{F}/savings", json=body, headers=_h(created)), 201)


def _clear_production(engine, created, equipment_id):
    """시드의 월 생산 기록이 제 기록에 더해지지 않게 그 설비의 기록을 비운다."""
    with engine.begin() as c:
        c.execute(
            text(
                "DELETE FROM fems.production_record "
                "WHERE workspace_id=:w AND generation_id=:g AND equipment_id=:e"
            ),
            {**_scope(created), "e": equipment_id},
        )


def _production(engine, created, equipment_id, key, start, end, qty):
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO fems.production_record (workspace_id,generation_id,source_key,"
                "version_no,equipment_id,item_code,period_start,period_end,production_qty,"
                "unit,status,confirmed_at,source) VALUES (:w,:g,:k,1,:e,'FG-T',:s,:t,:q,"
                "'EA','confirmed',now(),'MANUAL')"
            ),
            {
                **_scope(created),
                "k": key,
                "e": equipment_id,
                "s": start,
                "t": end,
                "q": qty,
            },
        )


# ---------- 절감 활동 (F-19) ----------


def test_baseline_must_end_before_the_start(space):
    """비교 전 기간이 시행 뒤까지 이어지면 전·후가 겹친다."""
    client, created, _ = space
    body = _saving_body(energySourceId=_elec_id(client), baselineEndOn="2026-09-05")
    response = client.post(f"{F}/savings", json=body, headers=_h(created))
    assert response.status_code == 400
    assert "baselineEndOn" in response.json()["error"]["details"]["fields"]


def test_saving_code_is_unique(space):
    client, created, _ = space
    first = _create_saving(client, created)
    again = client.post(
        f"{F}/savings",
        json=_saving_body(energySourceId=_elec_id(client), code=first["code"]),
        headers=_h(created),
    )
    assert again.status_code == 409


def test_saving_moves_forward_and_can_be_cancelled(space):
    client, created, _ = space
    saving = _create_saving(client, created)
    assert saving["status"] == "PLANNED"
    active = _ok(client.post(f"{F}/savings/{saving['id']}/start", headers=_h(created)))
    assert active["status"] == "ACTIVE"
    assert (
        client.post(
            f"{F}/savings/{saving['id']}/start", headers=_h(created)
        ).status_code
        == 409
    )
    cancelled = _ok(
        client.post(f"{F}/savings/{saving['id']}/cancel", headers=_h(created))
    )
    assert cancelled["status"] == "CANCELLED"
    assert (
        client.post(
            f"{F}/savings/{saving['id']}/cancel", headers=_h(created)
        ).status_code
        == 409
    )


def test_only_an_active_saving_can_be_verified(space):
    client, created, _ = space
    saving = _create_saving(client, created)
    response = client.post(f"{F}/savings/{saving['id']}/verify", headers=_h(created))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "BAD_STATE"


def test_verification_waits_for_the_after_period(space):
    """비교 후 기간이 계측보다 앞서 있으면 검증할 수 없다."""
    client, created, _ = space
    latest = _latest_day(client)
    # 시행일이 최신 계측일이라 비교 후 기간(4일)의 대부분이 아직 계측 밖이다.
    saving = _create_saving(
        client,
        created,
        baselineStartOn=(latest - timedelta(days=4)).isoformat(),
        baselineEndOn=latest.isoformat(),
        startOn=latest.isoformat(),
    )
    _ok(client.post(f"{F}/savings/{saving['id']}/start", headers=_h(created)))
    response = client.post(f"{F}/savings/{saving['id']}/verify", headers=_h(created))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "PERIOD_NOT_ELAPSED"


def test_verification_normalizes_by_production(space):
    """실제 절감 = (비교 전 원단위 − 비교 후 원단위) × 비교 후 생산량, 연 환산."""
    client, created, engine = space
    equipment_id, source_id = _busy_equipment(engine, created)
    _clear_production(engine, created, equipment_id)
    _production(
        engine,
        created,
        equipment_id,
        "T-A",
        "2026-08-25 00:00+09",
        "2026-09-01 00:00+09",
        700,
    )
    _production(
        engine,
        created,
        equipment_id,
        "T-B",
        "2026-09-01 00:00+09",
        "2026-09-08 00:00+09",
        1400,
    )
    saving = _create_saving(
        client, created, equipmentId=equipment_id, energySourceId=source_id
    )
    _ok(client.post(f"{F}/savings/{saving['id']}/start", headers=_h(created)))
    done = _ok(client.post(f"{F}/savings/{saving['id']}/verify", headers=_h(created)))

    assert done["status"] == "VERIFIED" and done["verifiedAt"]
    ev = done["evidence"]
    assert ev["productionAdjusted"] is True and ev["days"] == 7
    e0, e1 = Decimal(ev["baseline"]["energy"]), Decimal(ev["after"]["energy"])
    p0, p1 = Decimal(ev["baseline"]["production"]), Decimal(ev["after"]["production"])
    assert p0 == 700 and p1 == 1400, "기록이 기간 안에 들어와 일할 계산이 1이어야 한다"
    # 생산이 두 배라 원단위가 절반이 된다: (e0/700 − e1/1400) × 1400 = 2·e0 − e1
    assert abs(Decimal(ev["periodSaving"]) - (2 * e0 - e1)) < Decimal("0.001")
    annual = Decimal(done["measuredSaving"])
    assert abs(annual - Decimal(ev["periodSaving"]) * 365 / 7) < Decimal("0.01")


def test_verification_without_production_is_refused(space):
    """생산량이 없으면 원단위를 낼 수 없다. 사용량 차이로 대신하지 않는다."""
    client, created, engine = space
    equipment_id, source_id = _busy_equipment(engine, created)
    _clear_production(engine, created, equipment_id)
    saving = _create_saving(
        client, created, equipmentId=equipment_id, energySourceId=source_id
    )
    _ok(client.post(f"{F}/savings/{saving['id']}/start", headers=_h(created)))
    response = client.post(f"{F}/savings/{saving['id']}/verify", headers=_h(created))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "NO_PRODUCTION"


def test_site_wide_saving_says_it_is_not_production_adjusted(space):
    """설비가 없는 과제는 보정할 생산량이 없다. 사용량 차이를 쓰고 응답이 그렇다고 밝힌다."""
    client, created, _ = space
    saving = _create_saving(client, created)
    _ok(client.post(f"{F}/savings/{saving['id']}/start", headers=_h(created)))
    done = _ok(client.post(f"{F}/savings/{saving['id']}/verify", headers=_h(created)))
    assert done["evidence"]["productionAdjusted"] is False
    assert done["evidence"]["baseline"]["production"] is None


def test_verified_saving_is_frozen(space):
    client, created, _ = space
    saving = _create_saving(client, created)
    _ok(client.post(f"{F}/savings/{saving['id']}/start", headers=_h(created)))
    _ok(client.post(f"{F}/savings/{saving['id']}/verify", headers=_h(created)))
    for action in ("verify", "cancel", "start"):
        response = client.post(
            f"{F}/savings/{saving['id']}/{action}", headers=_h(created)
        )
        assert response.status_code == 409, action


# ---------- 월간 에너지 검토 (F-20) ----------


def _review_month(client) -> str:
    return _ok(client.get(f"{F}/billing"))["period"]["to"]


def _review(client, created, month, **extra):
    return client.post(
        f"{F}/energy-reviews", json={"month": month, **extra}, headers=_h(created)
    )


def test_review_snapshot_keeps_factors_apart(space):
    client, created, _ = space
    month = _review_month(client)
    review = _ok(_review(client, created, month, issues="냉각수 펌프 점검"), 201)
    assert review["status"] == "draft" and review["version"] == 1
    assert Decimal(review["primaryEnergyToe"]) > 0
    assert Decimal(review["emissionTco2e"]) > 0
    assert Decimal(review["energyCost"]) > 0
    assert "냉각수 펌프 점검" in review["issues"]
    # 시드는 한 달치뿐이라 달 전체가 아니다 — 확정본에 남는 칸에 그 사실을 적는다.
    assert review["coverage"]["partial"] is True
    assert "※ 계측" in review["issues"]


def test_review_without_readings_is_refused(space):
    client, created, _ = space
    response = _review(client, created, "1999-01")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "NO_READINGS"


def test_missing_factor_blocks_the_review(space):
    """계수가 빠진 에너지원이 있으면 부분 합계를 확정본에 남기지 않는다."""
    client, created, engine = space
    with engine.begin() as c:
        c.execute(
            text(
                "DELETE FROM fems.energy_factor WHERE workspace_id=:w AND generation_id=:g "
                "AND factor_kind='EMISSION'"
            ),
            _scope(created),
        )
    response = _review(client, created, _review_month(client))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "INCOMPLETE"


def test_new_review_draft_replaces_the_old_one(space):
    client, created, _ = space
    month = _review_month(client)
    _ok(_review(client, created, month), 201)
    _ok(_review(client, created, month, issues="다시"), 201)
    drafts = [
        r
        for r in _ok(client.get(f"{F}/energy-reviews"))
        if r["status"] == "draft" and r["reviewMonth"] == month
    ]
    assert len(drafts) == 1 and "다시" in drafts[0]["issues"]


def test_confirmed_review_is_superseded_by_a_new_version(space):
    client, created, _ = space
    month = _review_month(client)
    first = _ok(_review(client, created, month), 201)
    confirmed = _ok(
        client.post(f"{F}/energy-reviews/{first['id']}/confirm", headers=_h(created))
    )
    assert confirmed["status"] == "confirmed" and confirmed["confirmedAt"]
    again = client.post(
        f"{F}/energy-reviews/{first['id']}/confirm", headers=_h(created)
    )
    assert again.status_code == 409, "확정본은 다시 확정하지 않는다"

    second = _ok(_review(client, created, month, issues="정정"), 201)
    assert second["version"] == 2
    _ok(client.post(f"{F}/energy-reviews/{second['id']}/confirm", headers=_h(created)))
    states = {
        r["version"]: r["status"]
        for r in _ok(client.get(f"{F}/energy-reviews"))
        if r["reviewMonth"] == month
    }
    assert states == {1: "superseded", 2: "confirmed"}


# ---------- 온실가스 명세서 (F-21) ----------


def _ghg(client, created, year="2026"):
    return client.post(f"{F}/ghg-inventories", json={"year": year}, headers=_h(created))


def test_ghg_scopes_follow_the_source_kind(space):
    """Scope 1 = 연료, Scope 2 = 전력·열. 합계는 줄의 합이다."""
    client, created, _ = space
    ghg = _ok(_ghg(client, created), 201)
    scopes = {ln["sourceCode"]: ln["scope"] for ln in ghg["lines"]}
    assert scopes.get("ELEC") == 2
    assert scopes.get("GAS", 1) == 1
    one = sum(Decimal(ln["emissionTco2e"]) for ln in ghg["lines"] if ln["scope"] == 1)
    two = sum(Decimal(ln["emissionTco2e"]) for ln in ghg["lines"] if ln["scope"] == 2)
    assert Decimal(ghg["scope1Tco2e"]) == one
    assert Decimal(ghg["scope2Tco2e"]) == two
    assert two > 0


def test_ghg_uses_the_factor_of_that_year(space):
    client, created, _ = space
    ghg = _ok(_ghg(client, created, "2026"), 201)
    elec = [ln for ln in ghg["lines"] if ln["sourceCode"] == "ELEC"]
    assert elec and all(Decimal(ln["factorValue"]) == Decimal("0.00046") for ln in elec)


def test_ghg_says_when_the_year_is_not_covered(space):
    """시드는 한 달치다. '연간 명세서'가 연 전체가 아님을 응답이 밝힌다."""
    client, created, _ = space
    ghg = _ok(_ghg(client, created), 201)
    assert ghg["coverage"]["partial"] is True
    assert 0 < ghg["coverage"]["days"] < 365


def test_ghg_without_readings_is_refused(space):
    client, created, _ = space
    response = _ghg(client, created, "1999")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "NO_READINGS"


def test_ghg_missing_factor_blocks_the_inventory(space):
    client, created, engine = space
    with engine.begin() as c:
        c.execute(
            text(
                "DELETE FROM fems.energy_factor WHERE workspace_id=:w AND generation_id=:g "
                "AND factor_kind='EMISSION' AND effective_year='2026'"
            ),
            _scope(created),
        )
    response = _ghg(client, created)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "INCOMPLETE"


def test_ghg_confirm_then_new_version(space):
    client, created, _ = space
    first = _ok(_ghg(client, created), 201)
    _ok(client.post(f"{F}/ghg-inventories/{first['id']}/confirm", headers=_h(created)))
    second = _ok(_ghg(client, created), 201)
    assert second["version"] == 2
    _ok(client.post(f"{F}/ghg-inventories/{second['id']}/confirm", headers=_h(created)))
    states = {
        r["version"]: r["status"]
        for r in _ok(client.get(f"{F}/ghg-inventories"))
        if r["inventoryYear"] == "2026"
    }
    assert states == {1: "superseded", 2: "confirmed"}
    assert _ok(client.get(f"{F}/ghg-inventories/{second['id']}"))["lines"]
