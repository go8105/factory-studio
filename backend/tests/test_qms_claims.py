"""QMS-1e: 고객 클레임(Q-09)과 공급처 품질(Q-10) — DSN-14 F41~F43·F05·F14·F51.

클레임은 **QMS가 소유**한다(Q4). 접수 → 조사 → 회신 → 종결이고, **조사 시작이 곧
고객 발생 부적합 보고 생성**이다(DB_POLICY). 공급처 검사 수준은 적용일 이력이고
현재 수준은 저장하지 않고 조회로 고른다.
"""

from itertools import count

import pytest
from fs.common.auth import AuthContext
from fs.qms import interface as qms
from sqlalchemy import text

Q = "/api/v1/qms"
_keys = count()
TODAY = "2026-09-24"  # guest_space fixture의 FS_TODAY

QMS_TABLES = (
    "scar",
    "supplier_level",
    "supplier_rating",
    "capa",
    "ncr",
    "claim",
    "quality_hold",
    "inspection_value",
    "inspection",
    "inspection_spec_item",
    "inspection_spec",
)


@pytest.fixture
def qms_space(guest_space):
    client, created, engine = guest_space
    with engine.begin() as connection:
        for table in QMS_TABLES:
            connection.execute(
                text(
                    f"DELETE FROM qms.{table} WHERE workspace_id=:w AND generation_id=:g"
                ),
                {"w": created["workspaceId"], "g": created["generationId"]},
            )
    return client, created, engine


def _call(client, created, method: str, path: str, body=None):
    return client.request(
        method,
        f"{Q}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": f"k{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _fields(response) -> dict:
    return response.json()["error"]["details"]["fields"]


def _claim(client, created, **extra) -> dict:
    body = {
        "customerCode": "CUST-001",
        "itemCode": "FG-C100",
        "qty": "20",
        "severity": "MAJOR",
        "description": "핀이 휘어 체결이 되지 않는다는 고객 연락입니다.",
        **extra,
    }
    return _ok(_call(client, created, "POST", "/claims", body), 201)


def _investigated(client, created, claim_id: int) -> dict:
    return _ok(
        _call(
            client,
            created,
            "POST",
            f"/claims/{claim_id}/investigation",
            {"description": "반송품을 받아 치수를 재니 핀 피치가 상한을 벗어났습니다."},
        )
    )


def _responded(client, created, claim_id: int) -> dict:
    _investigated(client, created, claim_id)
    return _ok(
        _call(
            client,
            created,
            "POST",
            f"/claims/{claim_id}/response",
            {"response": "해당 LOT을 회수하고 금형을 교체했습니다."},
        )
    )


# ---------- 클레임 (Q-09) ----------


def test_claim_starts_as_received(qms_space):
    client, created, _ = qms_space
    claim = _claim(client, created)
    assert claim["status"] == "RECEIVED" and claim["claimNo"].startswith("CL-20260924-")
    assert claim["receivedOn"] == TODAY and claim["ncrCount"] == 0
    assert claim["respondedOn"] is None and claim["closedAt"] is None


def test_investigation_creates_the_customer_ncr(qms_space):
    """조사 시작 = 고객 발생 부적합 생성. 클레임 없이 그 부적합을 만들 길은 없다."""
    client, created, _ = qms_space
    claim = _claim(client, created, lotNo="LT-0013")
    started = _investigated(client, created, claim["id"])
    assert started["status"] == "INVESTIGATING" and started["ncrId"]

    detail = _ok(client.get(f"{Q}/claims/{claim['id']}"))
    assert len(detail["ncrs"]) == 1
    ncr = detail["ncrs"][0]
    assert ncr["origin"] == "CUSTOMER" and ncr["claimId"] == claim["id"]
    assert ncr["lotNo"] == "LT-0013" and ncr["qty"] == claim["qty"]

    # Q-07에서 직접 고객 발생 부적합을 만들 수는 없다.
    direct = _call(
        client,
        created,
        "POST",
        "/ncrs",
        {
            "origin": "CUSTOMER",
            "itemCode": "FG-C100",
            "qty": "5",
            "description": "직접 만들기",
        },
    )
    assert direct.status_code == 409 and _reason(direct) == "CLAIM_REQUIRED"


def test_investigation_runs_only_once(qms_space):
    client, created, _ = qms_space
    claim = _claim(client, created)
    _investigated(client, created, claim["id"])
    again = _call(
        client,
        created,
        "POST",
        f"/claims/{claim['id']}/investigation",
        {"description": "또 조사"},
    )
    assert again.status_code == 409 and _reason(again) == "NOT_RECEIVED"


def test_response_needs_an_investigation_first(qms_space):
    """확인하지 않고 고객에게 답하지 않는다."""
    client, created, _ = qms_space
    claim = _claim(client, created)
    early = _call(
        client,
        created,
        "POST",
        f"/claims/{claim['id']}/response",
        {"response": "죄송합니다"},
    )
    assert early.status_code == 409 and _reason(early) == "NOT_INVESTIGATING"


def test_responded_claim_is_no_longer_editable(qms_space):
    client, created, _ = qms_space
    claim = _claim(client, created)
    responded = _responded(client, created, claim["id"])
    assert responded["status"] == "RESPONDED" and responded["respondedOn"] == TODAY
    edit = _call(client, created, "PATCH", f"/claims/{claim['id']}", {"qty": "30"})
    assert edit.status_code == 409 and _reason(edit) == "CLAIM_RESPONDED"


def test_claim_closes_only_after_its_ncrs_close(qms_space):
    """부적합이 열려 있으면 클레임을 닫지 않는다 — 조치가 남은 채로 끝내지 않는다."""
    client, created, _ = qms_space
    claim = _claim(client, created)
    _responded(client, created, claim["id"])
    blocked = _call(client, created, "POST", f"/claims/{claim['id']}/closure")
    assert blocked.status_code == 409 and _reason(blocked) == "NCR_OPEN"
    assert blocked.json()["error"]["details"]["open"] == 1

    ncr_id = _ok(client.get(f"{Q}/claims/{claim['id']}"))["ncrs"][0]["id"]
    capa = _ok(
        _call(
            client,
            created,
            "POST",
            "/capas",
            {
                "ncrId": ncr_id,
                "kind": "CORRECTIVE",
                "rootCause": "금형 마모",
                "action": "금형 교체",
                "ownerName": "김품질",
                "dueOn": "2026-10-10",
            },
        ),
        201,
    )
    _ok(_call(client, created, "POST", f"/capas/{capa['id']}/completion"))
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/capas/{capa['id']}/verification",
            {"effective": True, "note": "재발 없음"},
        )
    )
    _ok(_call(client, created, "POST", f"/ncrs/{ncr_id}/closure"))
    closed = _ok(_call(client, created, "POST", f"/claims/{claim['id']}/closure"))
    assert closed["status"] == "CLOSED" and closed["closedAt"]


def test_claim_detail_carries_the_lot_trace(qms_space):
    """LOT이 있으면 MES 계보를 함께 준다(F43). 없는 LOT이면 trace는 None이다."""
    client, created, _ = qms_space
    lot_no = _ok(client.get(f"{Q}/lookups/mes-lots"))[0]["lotNo"]
    traced = _claim(client, created, lotNo=lot_no)
    detail = _ok(client.get(f"{Q}/claims/{traced['id']}"))
    assert detail["mesEnabled"] is True
    assert detail["trace"]["lotNo"] == lot_no
    assert detail["trace"]["materials"]

    unknown = _claim(client, created, lotNo="없는LOT")
    assert _ok(client.get(f"{Q}/claims/{unknown['id']}"))["trace"] is None


def test_crm_reads_claims_through_the_interface(qms_space):
    """CRM은 클레임을 읽기만 한다. QMS를 끄면 None이다."""
    client, created, engine = qms_space
    claim = _claim(client, created)
    context = AuthContext(
        actor_kind="GUEST",
        actor_key="test",
        workspace_id=created["workspaceId"],
        generation_id=created["generationId"],
        user_id=None,
        roles=("GUEST",),
        token=None,
    )
    with engine.begin() as c:
        rows = qms.claims(c, context, "CUST-001")
        assert [r["claimNo"] for r in rows] == [claim["claimNo"]]
        assert qms.claims(c, context, "없는고객") == []
        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false "
                "WHERE workspace_id=:w AND module_key='qms'"
            ),
            {"w": created["workspaceId"]},
        )
        assert qms.claims(c, context) is None


# ---------- 공급처 품질 (Q-10) ----------


def _level(client, created, **extra) -> dict:
    body = {
        "partnerCode": "SUP-001",
        "level": "NORMAL",
        "validFrom": "2026-09-01",
        "reason": "신규 거래 시작",
        **extra,
    }
    return _ok(_call(client, created, "POST", "/supplier-levels", body), 201)


def test_current_level_is_the_latest_applied_row(qms_space):
    """현재 수준은 저장하지 않는다 — 적용일이 오늘 이하인 최신 행이다."""
    client, created, _ = qms_space
    _level(client, created)
    _level(
        client,
        created,
        level="TIGHTENED",
        validFrom="2026-09-20",
        reason="연속 불합격",
    )
    # 아직 오지 않은 적용일은 현재가 아니다.
    _level(client, created, level="EXEMPT", validFrom="2026-12-01", reason="면제 예정")
    rows = _ok(client.get(f"{Q}/supplier-levels?partnerCode=SUP-001"))
    current = [r for r in rows if r["isCurrent"]]
    assert len(current) == 1 and current[0]["level"] == "TIGHTENED"


def test_level_is_scoped_per_item(qms_space):
    """품목별 수준과 공급처 전체 수준은 따로 간다."""
    client, created, _ = qms_space
    _level(client, created)
    _level(client, created, itemCode="FG-C100", level="EXEMPT", reason="품목 면제")
    rows = _ok(client.get(f"{Q}/supplier-levels"))
    current = {r["itemCode"]: r["level"] for r in rows if r["isCurrent"]}
    assert current == {None: "NORMAL", "FG-C100": "EXEMPT"}


def test_same_partner_item_and_date_is_rejected(qms_space):
    client, created, _ = qms_space
    _level(client, created)
    again = _call(
        client,
        created,
        "POST",
        "/supplier-levels",
        {
            "partnerCode": "SUP-001",
            "level": "TIGHTENED",
            "validFrom": "2026-09-01",
            "reason": "같은 날",
        },
    )
    assert again.status_code == 400 and "validFrom" in _fields(again)


def test_rating_is_empty_until_incoming_inspections_exist(qms_space):
    """수입 검사가 없으면 평가할 공급처가 없다 — 0점이 아니라 '아직 아님'이다."""
    client, created, _ = qms_space
    result = _ok(_call(client, created, "POST", "/supplier-ratings?month=2026-09"))
    assert result == {"month": "2026-09", "partners": []}
    assert _ok(client.get(f"{Q}/supplier-ratings")) == []


def test_rating_grades_and_suggests_from_incoming_inspections(qms_space):
    """불합격 비율로 등급을 매기고, **최신 연속** 불합격 2건이면 강화를 제안한다."""
    client, created, engine = qms_space
    # 시각 순서대로 넣는다 — 최신 두 건이 불합격이어야 강화 제안이 나온다.
    _seed_incoming(engine, created, results=["PASS", "PASS", "FAIL", "FAIL"])
    _ok(_call(client, created, "POST", "/supplier-ratings?month=2026-09"))
    rows = _ok(client.get(f"{Q}/supplier-ratings?month=2026-09"))
    assert len(rows) == 1
    rating = rows[0]
    assert rating["partnerCode"] == "SUP-001"
    assert rating["lotCount"] == 4 and rating["failedLotCount"] == 2
    assert rating["grade"] == "D"  # 불합격 50%
    assert rating["suggestedLevel"] == "TIGHTENED"


def test_rating_recalculation_overwrites_the_month(qms_space):
    client, created, engine = qms_space
    _seed_incoming(engine, created, results=["PASS"])
    _ok(_call(client, created, "POST", "/supplier-ratings?month=2026-09"))
    _seed_incoming(engine, created, results=["FAIL"], start=10)
    _ok(_call(client, created, "POST", "/supplier-ratings?month=2026-09"))
    rows = _ok(client.get(f"{Q}/supplier-ratings?month=2026-09"))
    assert len(rows) == 1 and rows[0]["lotCount"] == 2


def _seed_incoming(engine, created, results: list[str], start: int = 0) -> None:
    """수입 검사는 1f에서 열린다. 평가 계산만 보려고 합성 행을 직접 넣는다."""
    scope = {"w": created["workspaceId"], "g": created["generationId"]}
    with engine.begin() as c:
        spec_id = c.execute(
            text(
                "INSERT INTO qms.inspection_spec(workspace_id,generation_id,item_code,"
                "item_name,version_no,status,published_at,inspection_kind) "
                "VALUES (:w,:g,'RM-PBT','PBT 수지',1,'published',now(),'INCOMING') "
                "ON CONFLICT DO NOTHING RETURNING id"
            ),
            scope,
        ).scalar()
        if spec_id is None:
            spec_id = c.execute(
                text(
                    "SELECT id FROM qms.inspection_spec WHERE workspace_id=:w "
                    "AND generation_id=:g AND inspection_kind='INCOMING'"
                ),
                scope,
            ).scalar_one()
        for index, result in enumerate(results):
            c.execute(
                text(
                    "INSERT INTO qms.inspection(workspace_id,generation_id,inspection_no,"
                    "source,lot_no,item_code,item_name,lot_qty,unit,sample_qty,spec_id,"
                    "status,result,inspected_on,inspection_month,confirmed_at,"
                    "inspection_kind,partner_code,source_ref,defect_count) "
                    "VALUES (:w,:g,:no,'WMS',:lot,'RM-PBT','PBT 수지',100,'KG',10,:spec,"
                    "'confirmed',:result,DATE '2026-09-10','2026-09',"
                    "timestamptz '2026-09-10 09:00+09' + make_interval(hours => :h),"
                    "'INCOMING','SUP-001',:ref,:defects)"
                ),
                {
                    **scope,
                    "no": f"QI-SEED-{start + index:03d}",
                    "lot": f"IN-{start + index:03d}",
                    "spec": spec_id,
                    "result": result,
                    "h": start + index,
                    "ref": f"IN-NOTICE:{start + index}",
                    "defects": 2 if result == "FAIL" else 0,
                },
            )


# ---------- 시정 요구 (SCAR) ----------


def _scar(client, created, **extra) -> dict:
    body = {"partnerCode": "SUP-001", "dueOn": "2026-10-10", **extra}
    return _ok(_call(client, created, "POST", "/scars", body), 201)


def test_scar_runs_open_responded_closed(qms_space):
    client, created, _ = qms_space
    scar = _scar(client, created)
    assert scar["status"] == "OPEN" and scar["scarNo"].startswith("SC-20260924-")
    assert scar["issuedOn"] == TODAY

    early = _call(client, created, "POST", f"/scars/{scar['id']}/closure")
    assert early.status_code == 409 and _reason(early) == "SCAR_NOT_RESPONDED"

    responded = _ok(
        _call(
            client,
            created,
            "POST",
            f"/scars/{scar['id']}/response",
            {"response": "금형을 수리하고 전수 검사를 했습니다."},
        )
    )
    assert responded["status"] == "RESPONDED" and responded["respondedOn"] == TODAY
    closed = _ok(_call(client, created, "POST", f"/scars/{scar['id']}/closure"))
    assert closed["status"] == "CLOSED" and closed["closedAt"]


def test_scar_due_date_must_follow_the_issue_date(qms_space):
    client, created, _ = qms_space
    response = _call(
        client,
        created,
        "POST",
        "/scars",
        {"partnerCode": "SUP-001", "issuedOn": "2026-09-20", "dueOn": "2026-09-01"},
    )
    assert response.status_code == 400 and "dueOn" in _fields(response)


def test_scar_can_cite_a_nonconformance(qms_space):
    client, created, _ = qms_space
    ncr = _ok(
        _call(
            client,
            created,
            "POST",
            "/ncrs",
            {
                "origin": "PROCESS",
                "itemCode": "FG-C100",
                "qty": "5",
                "description": "수입 자재 탓으로 보이는 공정 불량입니다.",
            },
        ),
        201,
    )
    scar = _scar(client, created, ncrId=ncr["id"])
    assert scar["ncrNo"] == ncr["ncrNo"]
    missing = _call(
        client,
        created,
        "POST",
        "/scars",
        {"partnerCode": "SUP-001", "dueOn": "2026-10-10", "ncrId": 999999},
    )
    assert missing.status_code == 400 and "ncrId" in _fields(missing)


def test_scar_counts_pull_the_grade_down(qms_space):
    """시정 요구가 있으면 한 단계 내린다 — 불합격이 없어도 A가 아니다."""
    client, created, engine = qms_space
    _seed_incoming(engine, created, results=["PASS", "PASS"])
    _scar(client, created, issuedOn="2026-09-15")
    _ok(_call(client, created, "POST", "/supplier-ratings?month=2026-09"))
    rating = _ok(client.get(f"{Q}/supplier-ratings?month=2026-09"))[0]
    assert rating["failedLotCount"] == 0 and rating["scarCount"] == 1
    assert rating["grade"] == "B"
