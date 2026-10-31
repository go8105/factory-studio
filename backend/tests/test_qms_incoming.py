"""QMS-1f: 검사 종류·AQL 샘플링·수입 검사 — DSN-14 F04·F11·F12·Q1·Q2.

AQL 표는 **코드 상수**다(DB 아님). 기준은 품목·검사 종류당 1개이고 **반품·초품은 출하
기준을 쓴다**. 수입 검사 대상은 WMS 격리 줄 중 **면제가 아닌 공급처**의 것이다.
"""

from itertools import count

import pytest
from fs.qms import sampling
from sqlalchemy import text

Q = "/api/v1/qms"
_keys = count()

ITEMS = [
    {"name": "외관", "method": "PASS_FAIL"},
    {
        "name": "함수율",
        "method": "RANGE",
        "lowerLimit": "0.01",
        "upperLimit": "0.05",
        "unit": "%",
    },
]


@pytest.fixture
def qms_space(guest_space):
    client, created, engine = guest_space
    with engine.begin() as connection:
        for table in (
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
        ):
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


def _spec(client, created, item_code: str, kind="OUTGOING", aql=None) -> dict:
    body = {
        "itemCode": item_code,
        "itemName": "자재" if kind == "INCOMING" else "완제품",
        "inspectionKind": kind,
        "items": ITEMS,
    }
    if aql:
        body["aql"] = aql
    draft = _ok(_call(client, created, "POST", "/inspection-specs", body), 201)
    return _ok(
        _call(client, created, "POST", f"/inspection-specs/{draft['id']}/publish")
    )


def _waiting(client) -> dict:
    return _ok(client.get(f"{Q}/lookups/incoming-lots"))


# ---------- AQL 표 (코드 상수) ----------


def test_aql_table_matches_the_standard_plans():
    """널리 쓰이는 KS Q ISO 2859-1(일반 수준 II·보통) 계획과 같아야 한다."""
    for lot, aql, size, accept in (
        (500, "1.0", 50, 1),
        (500, "2.5", 50, 3),
        (1200, "2.5", 80, 5),
        (3200, "1.0", 125, 3),
        (3200, "0.65", 125, 2),
        (10000, "1.0", 200, 5),
        (280, "1.0", 32, 0),
        (90, "2.5", 13, 0),
    ):
        plan = sampling.plan(lot, aql)
        assert (plan["sampleSize"], plan["acceptNumber"]) == (size, accept), (
            lot,
            aql,
            plan,
        )
        assert plan["rejectNumber"] == plan["acceptNumber"] + 1


def test_arrows_move_to_the_next_plan():
    """표의 화살표 — 너무 작은 로트에 엄격한 AQL이면 아래 계획으로 내려간다."""
    down = sampling.plan(10, "0.65")
    assert down["acceptNumber"] == 0 and down["isFullInspection"] is True
    up = sampling.plan(500000, "6.5")
    assert up["acceptNumber"] == 21


def test_sample_never_exceeds_the_lot():
    plan = sampling.plan(3, "1.0")
    assert plan["sampleSize"] == 3 and plan["isFullInspection"] is True


def test_tightened_uses_one_step_stricter_aql():
    """강화는 Table 2-B를 옮기지 않고 한 단계 엄격한 AQL로 대신한다."""
    normal = sampling.plan(1200, "2.5")
    tight = sampling.plan(1200, "2.5", "TIGHTENED")
    assert tight["aql"] == "1.5" and tight["acceptNumber"] < normal["acceptNumber"]
    strictest = sampling.plan(1200, "0.65", "TIGHTENED")
    assert strictest["aql"] == "0.65"  # 더 조일 곳이 없다


def test_judgement_needs_both_count_and_items():
    assert sampling.judge(1, 2, True) == "PASS"
    assert sampling.judge(3, 2, True) == "FAIL"  # 개수 초과
    assert sampling.judge(0, 2, False) == "FAIL"  # 필수 항목 불합격


def test_sampling_preview_endpoint(qms_space):
    client, _, _ = qms_space
    plan = _ok(client.get(f"{Q}/lookups/sampling-plan?lotQty=1200&aql=2.5"))
    assert plan["sampleSize"] == 80 and plan["acceptNumber"] == 5


# ---------- 검사 기준: 종류별 ----------


def test_spec_is_published_per_item_and_kind(qms_space):
    """같은 품목이라도 출하·수입 기준은 따로 게시된다 — 하나를 게시해도 다른 쪽은 그대로다."""
    client, created, _ = qms_space
    out = _spec(client, created, "FG-C100", "OUTGOING")
    incoming = _spec(client, created, "FG-C100", "INCOMING", aql="2.5")
    rows = _ok(client.get(f"{Q}/inspection-specs?itemCode=FG-C100"))
    published = {r["inspectionKind"]: r["status"] for r in rows}
    assert published == {"OUTGOING": "published", "INCOMING": "published"}
    assert out["aql"] is None and incoming["aql"] == "2.5"


def test_draft_is_unique_per_kind_not_per_item(qms_space):
    """출하 초안이 있어도 수입 초안은 따로 만들 수 있다."""
    client, created, _ = qms_space
    _ok(
        _call(
            client,
            created,
            "POST",
            "/inspection-specs",
            {"itemCode": "RM-PBT", "itemName": "수지", "items": ITEMS},
        ),
        201,
    )
    second = _call(
        client,
        created,
        "POST",
        "/inspection-specs",
        {
            "itemCode": "RM-PBT",
            "itemName": "수지",
            "inspectionKind": "INCOMING",
            "items": ITEMS,
        },
    )
    assert second.status_code == 201
    again = _call(
        client,
        created,
        "POST",
        "/inspection-specs",
        {"itemCode": "RM-PBT", "itemName": "수지", "items": ITEMS},
    )
    assert again.status_code == 409 and _reason(again) == "DRAFT_EXISTS"


# ---------- 수입 검사 대기 ----------


def _source(client) -> dict:
    waiting = _waiting(client)
    assert waiting["wmsEnabled"] is True
    assert waiting["rows"], "시드에 격리된 입고 줄이 있어야 한다"
    return waiting["rows"][0]


def test_waiting_list_comes_from_wms_quarantine(qms_space):
    client, _, _ = qms_space
    row = _source(client)
    assert row["sourceRef"] and row["partnerCode"]
    assert row["level"] == "NORMAL"  # 수준을 정하지 않으면 보통
    # 목록에 남았다는 것이 곧 검사 대상이라는 뜻이다(면제는 아래 테스트에서 빠진다).


def test_exempt_supplier_drops_out_of_the_waiting_list(qms_space):
    """면제 공급처는 검사하지 않는다 — 목록에서 빠진다(Q1)."""
    client, created, _ = qms_space
    row = _source(client)
    _ok(
        _call(
            client,
            created,
            "POST",
            "/supplier-levels",
            {
                "partnerCode": row["partnerCode"],
                "level": "EXEMPT",
                "validFrom": "2026-09-01",
                "reason": "연속 합격으로 면제",
            },
        ),
        201,
    )
    refs = {r["sourceRef"] for r in _waiting(client)["rows"]}
    assert row["sourceRef"] not in refs


def test_item_level_beats_the_partner_wide_level(qms_space):
    """품목별 수준이 공급처 전체 수준을 이긴다."""
    client, created, _ = qms_space
    row = _source(client)
    for body in (
        {
            "partnerCode": row["partnerCode"],
            "level": "EXEMPT",
            "validFrom": "2026-09-01",
            "reason": "전체 면제",
        },
        {
            "partnerCode": row["partnerCode"],
            "itemCode": row["itemCode"],
            "level": "TIGHTENED",
            "validFrom": "2026-09-02",
            "reason": "이 품목만 강화",
        },
    ):
        _ok(_call(client, created, "POST", "/supplier-levels", body), 201)
    found = next(
        r for r in _waiting(client)["rows"] if r["sourceRef"] == row["sourceRef"]
    )
    assert found["level"] == "TIGHTENED"


# ---------- 수입 검사 만들기·판정 ----------


def test_incoming_inspection_takes_its_sample_size_from_the_aql_table(qms_space):
    client, created, _ = qms_space
    row = _source(client)
    _spec(client, created, row["itemCode"], "INCOMING", aql="2.5")
    inspection = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections/incoming",
            {"sourceRef": row["sourceRef"]},
        ),
        201,
    )
    plan = sampling.plan(sampling.lot_size_of(row["qty"]), "2.5")
    assert inspection["sampling"] == "AQL"
    assert inspection["sampleQty"] == f"{plan['sampleSize']}.000"
    assert inspection["acceptNumber"] == plan["acceptNumber"]
    assert inspection["rejectNumber"] == plan["acceptNumber"] + 1
    assert inspection["inspectionKind"] == "INCOMING"
    assert inspection["source"] == "WMS"
    assert inspection["partnerCode"] == row["partnerCode"]


def test_incoming_without_aql_needs_a_manual_sample(qms_space):
    client, created, _ = qms_space
    row = _source(client)
    _spec(client, created, row["itemCode"], "INCOMING")
    missing = _call(
        client,
        created,
        "POST",
        "/inspections/incoming",
        {"sourceRef": row["sourceRef"]},
    )
    assert missing.status_code == 400 and "sampleQty" in _fields(missing)
    inspection = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections/incoming",
            {"sourceRef": row["sourceRef"], "sampleQty": "2"},
        ),
        201,
    )
    assert inspection["sampling"] == "MANUAL" and inspection["acceptNumber"] is None


def test_incoming_needs_an_incoming_spec(qms_space):
    """출하 기준만 게시해 두면 수입 검사를 만들 수 없다 — 섞이지 않는다."""
    client, created, _ = qms_space
    row = _source(client)
    _spec(client, created, row["itemCode"], "OUTGOING")
    response = _call(
        client,
        created,
        "POST",
        "/inspections/incoming",
        {"sourceRef": row["sourceRef"]},
    )
    assert response.status_code == 409 and _reason(response) == "NO_PUBLISHED_SPEC"
    assert response.json()["error"]["details"]["inspectionKind"] == "INCOMING"


def test_one_inspection_per_inbound_line(qms_space):
    client, created, _ = qms_space
    row = _source(client)
    _spec(client, created, row["itemCode"], "INCOMING", aql="2.5")
    _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections/incoming",
            {"sourceRef": row["sourceRef"]},
        ),
        201,
    )
    assert row["sourceRef"] not in {r["sourceRef"] for r in _waiting(client)["rows"]}
    again = _call(
        client,
        created,
        "POST",
        "/inspections/incoming",
        {"sourceRef": row["sourceRef"]},
    )
    assert again.status_code == 400 and "sourceRef" in _fields(again)


def _aql_inspection(client, created) -> tuple[dict, dict]:
    row = _source(client)
    _spec(client, created, row["itemCode"], "INCOMING", aql="6.5")
    inspection = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections/incoming",
            {"sourceRef": row["sourceRef"]},
        ),
        201,
    )
    by_name = {v["name"]: v["specItemId"] for v in inspection["values"]}
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}",
            {
                "values": [
                    {"specItemId": by_name["외관"], "passValue": True},
                    {"specItemId": by_name["함수율"], "measuredValue": "0.03"},
                ]
            },
        )
    )
    return row, inspection


def test_aql_confirmation_needs_the_defect_count(qms_space):
    client, created, _ = qms_space
    _, inspection = _aql_inspection(client, created)
    missing = _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    assert missing.status_code == 400 and "defectCount" in _fields(missing)


def test_defect_count_decides_the_aql_result(qms_space):
    """항목이 모두 합격이어도 **시료 불량이 Ac를 넘으면 불합격**이다."""
    client, created, _ = qms_space
    _, inspection = _aql_inspection(client, created)
    over = inspection["acceptNumber"] + 1
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}/defect-count",
            {"defectCount": over},
        )
    )
    failed = _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )
    assert failed["result"] == "FAIL"
    assert failed["activeHold"]["lotNo"] == failed["lotNo"]


def test_defect_count_within_the_accept_number_passes(qms_space):
    client, created, _ = qms_space
    _, inspection = _aql_inspection(client, created)
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}/defect-count",
            {"defectCount": inspection["acceptNumber"]},
        )
    )
    passed = _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )
    assert passed["result"] == "PASS" and passed["activeHold"] is None


def test_defect_count_cannot_exceed_the_sample(qms_space):
    client, created, _ = qms_space
    _, inspection = _aql_inspection(client, created)
    response = _call(
        client,
        created,
        "PATCH",
        f"/inspections/{inspection['id']}/defect-count",
        {"defectCount": 9999},
    )
    assert response.status_code == 400 and "defectCount" in _fields(response)


def test_incoming_failure_opens_the_incoming_ncr_and_feeds_the_rating(qms_space):
    """수입 불합격이 **Q-07 수입 발생처와 Q-10 월 평가를 동시에 연다**(1d·1e가 기다리던 것)."""
    client, created, _ = qms_space
    row, inspection = _aql_inspection(client, created)
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}/defect-count",
            {"defectCount": inspection["acceptNumber"] + 1},
        )
    )
    confirmed = _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )

    sources = _ok(client.get(f"{Q}/ncrs/sources?origin=INCOMING"))
    assert confirmed["id"] in {r["id"] for r in sources["rows"]}
    ncr = _ok(
        _call(
            client,
            created,
            "POST",
            "/ncrs",
            {
                "origin": "INCOMING",
                "itemCode": confirmed["itemCode"],
                "qty": "1",
                "description": "수입 자재가 규격을 벗어났습니다.",
                "inspectionId": confirmed["id"],
            },
        ),
        201,
    )
    assert ncr["origin"] == "INCOMING"

    month = confirmed["inspectionMonth"]
    _ok(_call(client, created, "POST", f"/supplier-ratings?month={month}"))
    ratings = _ok(client.get(f"{Q}/supplier-ratings?month={month}"))
    rating = next(r for r in ratings if r["partnerCode"] == row["partnerCode"])
    assert rating["lotCount"] == 1 and rating["failedLotCount"] == 1
    assert rating["grade"] == "D"
