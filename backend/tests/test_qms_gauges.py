"""QMS-1c: 계측기·교정(Q-11)과 4M 변경(Q-12) — DSN-14 F61·F62·F06.

계측기 상태는 교정 결과가 바꾼다(불합격 → 수리 중, 수리 중이 합격 → 사용 중).
교정 도래는 저장하지 않고 **마지막 교정의 다음 기한**에서 파생한다.
4M 변경은 신고 → 승인/반려 → 초품 검사 합격 → 확인 완료로만 닫힌다.
"""

from itertools import count

import pytest
from sqlalchemy import text

Q = "/api/v1/qms"
_keys = count()
TODAY = "2026-09-24"  # guest_space fixture의 FS_TODAY


@pytest.fixture
def qms(guest_space):
    client, created, engine = guest_space
    with engine.begin() as connection:
        for table in (
            "calibration",
            "gauge",
            "change_notice",
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
    return client, created


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


def _gauge(client, created, code="CAL-001", **extra) -> dict:
    body = {
        "code": code,
        "name": "버니어 캘리퍼스",
        "gaugeKind": "버니어 캘리퍼스",
        "measureRange": "0~150 mm",
        "resolution": "0.01 mm",
        "calibrationCycleDays": 365,
        **extra,
    }
    return _ok(_call(client, created, "POST", "/gauges", body), 201)


def _calibrate(client, created, gauge_id: int, **extra):
    body = {"calibratedOn": TODAY, "result": "PASS", **extra}
    return _call(client, created, "POST", f"/gauges/{gauge_id}/calibrations", body)


# ---------- 계측기·교정 (Q-11) ----------


def test_gauge_without_calibration_has_no_due_date(qms):
    """교정 기록이 없으면 '기한 없음'이다. 0도 아니고 지난 것도 아니다."""
    client, created = qms
    _gauge(client, created)
    rows = _ok(client.get(f"{Q}/gauges"))
    assert len(rows) == 1
    assert rows[0]["dueState"] == "NONE"
    assert rows[0]["nextDueOn"] is None and rows[0]["lastCalibratedOn"] is None


def test_calibration_due_date_comes_from_the_cycle(qms):
    """기한을 적지 않으면 교정 주기로 정한다."""
    client, created = qms
    gauge = _gauge(client, created, calibrationCycleDays=10)
    saved = _ok(_calibrate(client, created, gauge["id"]), 201)
    assert saved["nextDueOn"] == "2026-10-04"
    detail = _ok(client.get(f"{Q}/gauges/{gauge['id']}"))
    assert detail["dueState"] == "SOON" and detail["dueInDays"] == 10
    assert [c["id"] for c in detail["calibrations"]] == [saved["id"]]


def test_overdue_and_ok_states(qms):
    """30일 이내면 임박, 지났으면 기한 경과다."""
    client, created = qms
    far = _gauge(client, created, code="CAL-FAR")
    near = _gauge(client, created, code="CAL-OLD", calibrationCycleDays=1)
    _ok(_calibrate(client, created, far["id"]), 201)
    _ok(_calibrate(client, created, near["id"], calibratedOn="2026-09-01"), 201)
    state = {r["code"]: r["dueState"] for r in _ok(client.get(f"{Q}/gauges"))}
    assert state == {"CAL-FAR": "OK", "CAL-OLD": "OVERDUE"}


def test_failed_calibration_sends_the_gauge_to_repair(qms):
    """불합격이면 수리 중으로 내리고, 수리 중이 합격하면 다시 사용 중으로 올린다."""
    client, created = qms
    gauge = _gauge(client, created)
    saved = _ok(
        _calibrate(
            client, created, gauge["id"], calibratedOn="2026-09-23", result="FAIL"
        ),
        201,
    )
    assert saved["gaugeStatus"] == "REPAIR"
    assert _ok(client.get(f"{Q}/gauges/{gauge['id']}"))["status"] == "REPAIR"
    again = _ok(_calibrate(client, created, gauge["id"]), 201)
    assert again["gaugeStatus"] == "ACTIVE"
    assert _ok(client.get(f"{Q}/gauges/{gauge['id']}"))["status"] == "ACTIVE"


def test_retired_gauge_takes_no_calibration(qms):
    client, created = qms
    gauge = _gauge(client, created, status="RETIRED")
    response = _calibrate(client, created, gauge["id"])
    assert response.status_code == 409
    assert _reason(response) == "GAUGE_RETIRED"


def test_calibration_date_rules(qms):
    """같은 날짜 두 번·미래 교정일·기한 역전은 막는다."""
    client, created = qms
    gauge = _gauge(client, created)
    _ok(_calibrate(client, created, gauge["id"]), 201)
    again = _calibrate(client, created, gauge["id"])
    assert again.status_code == 400 and "calibratedOn" in _fields(again)
    future = _calibrate(client, created, gauge["id"], calibratedOn="2026-12-31")
    assert future.status_code == 400 and "calibratedOn" in _fields(future)
    early = _calibrate(
        client,
        created,
        gauge["id"],
        calibratedOn="2026-09-23",
        nextDueOn="2026-09-01",
    )
    assert early.status_code == 400 and "nextDueOn" in _fields(early)


def test_gauge_code_is_unique(qms):
    client, created = qms
    _gauge(client, created)
    response = _call(
        client,
        created,
        "POST",
        "/gauges",
        {
            "code": "CAL-001",
            "name": "또 다른 계측기",
            "gaugeKind": "마이크로미터",
            "calibrationCycleDays": 180,
        },
    )
    assert response.status_code == 400 and "code" in _fields(response)


# ---------- 4M 변경 (Q-12) ----------

SPEC_ITEMS = [
    {"name": "외관", "method": "PASS_FAIL"},
    {
        "name": "핀 피치",
        "method": "RANGE",
        "lowerLimit": "2.48",
        "upperLimit": "2.52",
        "unit": "mm",
    },
]


def _notice(client, created, **extra) -> dict:
    body = {
        "changeType": "MATERIAL",
        "itemCode": "FG-C100",
        "description": "수지 공급처를 바꿉니다.",
        "effectiveOn": "2026-10-01",
        **extra,
    }
    return _ok(_call(client, created, "POST", "/change-notices", body), 201)


def _approved(client, created, **extra) -> dict:
    notice = _notice(client, created, **extra)
    return _ok(
        _call(
            client,
            created,
            "POST",
            f"/change-notices/{notice['id']}/decision",
            {"approve": True, "note": "적용 승인"},
        )
    )


def _publish_spec(client, created, item_code="FG-C100") -> dict:
    spec = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspection-specs",
            {"itemCode": item_code, "itemName": "완제품", "items": SPEC_ITEMS},
        ),
        201,
    )
    return _ok(
        _call(client, created, "POST", f"/inspection-specs/{spec['id']}/publish")
    )


def test_change_notice_starts_as_requested(qms):
    client, created = qms
    notice = _notice(client, created)
    assert notice["status"] == "REQUESTED" and notice["decidedAt"] is None
    assert notice["cnNo"].startswith("CN-20260924-")
    assert notice["requestedOn"] == TODAY
    rows = _ok(client.get(f"{Q}/change-notices?status=REQUESTED"))
    assert [r["id"] for r in rows] == [notice["id"]]


def test_effective_date_must_not_precede_the_request(qms):
    client, created = qms
    response = _call(
        client,
        created,
        "POST",
        "/change-notices",
        {
            "changeType": "MAN",
            "itemCode": "FG-C100",
            "description": "작업자 교체",
            "effectiveOn": "2026-09-01",
        },
    )
    assert response.status_code == 400 and "effectiveOn" in _fields(response)


def test_decided_notice_is_no_longer_editable(qms):
    """승인·반려하면 기록을 바꾸지 않는다."""
    client, created = qms
    approved = _approved(client, created)
    assert approved["status"] == "APPROVED" and approved["decidedAt"]
    response = _call(
        client,
        created,
        "PATCH",
        f"/change-notices/{approved['id']}",
        {"description": "역시 바꾸지 않습니다."},
    )
    assert response.status_code == 409 and _reason(response) == "NOT_REQUESTED"
    again = _call(
        client,
        created,
        "POST",
        f"/change-notices/{approved['id']}/decision",
        {"approve": False, "note": "뒤집기"},
    )
    assert again.status_code == 409 and _reason(again) == "ALREADY_DECIDED"


def test_rejection_needs_a_note(qms):
    client, created = qms
    notice = _notice(client, created)
    response = _call(
        client,
        created,
        "POST",
        f"/change-notices/{notice['id']}/decision",
        {"approve": False},
    )
    assert response.status_code == 400 and "note" in _fields(response)


def test_first_article_needs_approval_and_a_published_spec(qms):
    client, created = qms
    notice = _notice(client, created)
    body = {"lotNo": "FA-001", "lotQty": "10", "unit": "EA", "sampleQty": "3"}
    early = _call(
        client, created, "POST", f"/change-notices/{notice['id']}/first-article", body
    )
    assert early.status_code == 409 and _reason(early) == "NOT_APPROVED"

    approved = _approved(client, created, itemCode="FG-NOSPEC")
    no_spec = _call(
        client, created, "POST", f"/change-notices/{approved['id']}/first-article", body
    )
    assert no_spec.status_code == 409 and _reason(no_spec) == "NO_PUBLISHED_SPEC"


def test_verification_closes_only_on_a_passed_first_article(qms):
    """초품 검사가 확정·합격해야 확인 완료가 된다. 불합격이면 승인 상태 그대로다."""
    client, created = qms
    _publish_spec(client, created)
    approved = _approved(client, created)
    cn_id = approved["id"]
    inspection = _ok(
        _call(
            client,
            created,
            "POST",
            f"/change-notices/{cn_id}/first-article",
            {"lotNo": "FA-001", "lotQty": "10", "unit": "EA", "sampleQty": "3"},
        ),
        201,
    )
    assert inspection["source"] == "QMS"

    # 확정 전에는 고를 수 없다.
    early = _call(
        client,
        created,
        "POST",
        f"/change-notices/{cn_id}/verification",
        {"firstArticleInspectionId": inspection["id"]},
    )
    assert early.status_code == 400
    assert "firstArticleInspectionId" in _fields(early)

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
                    {"specItemId": by_name["핀 피치"], "measuredValue": "2.50"},
                ]
            },
        )
    )
    confirmed = _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )
    assert confirmed["result"] == "PASS"

    detail = _ok(client.get(f"{Q}/change-notices/{cn_id}"))
    assert [f["id"] for f in detail["firstArticles"]] == [inspection["id"]]

    verified = _ok(
        _call(
            client,
            created,
            "POST",
            f"/change-notices/{cn_id}/verification",
            {"firstArticleInspectionId": inspection["id"]},
        )
    )
    assert verified["status"] == "VERIFIED"
    assert verified["firstArticleNo"] == confirmed["inspectionNo"]


def test_first_article_is_not_an_outgoing_inspection(qms, guest_space):
    """초품은 종류가 FIRST_ARTICLE이고 원천이 신고 번호다 — 출하 검사와 섞이지 않는다."""
    client, created = qms
    _publish_spec(client, created)
    approved = _approved(client, created)
    inspection = _ok(
        _call(
            client,
            created,
            "POST",
            f"/change-notices/{approved['id']}/first-article",
            {"lotNo": "FA-002", "lotQty": "10", "unit": "EA", "sampleQty": "3"},
        ),
        201,
    )
    engine = guest_space[2]
    with engine.begin() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT inspection_kind, source_ref, sampling FROM qms.inspection "
                    "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
                ),
                {
                    "w": created["workspaceId"],
                    "g": created["generationId"],
                    "id": inspection["id"],
                },
            )
            .mappings()
            .one()
        )
    assert row["inspection_kind"] == "FIRST_ARTICLE"
    assert row["source_ref"] == approved["cnNo"] and row["sampling"] == "MANUAL"


# ---------- 검사에 사용한 계측기 (QMS-1g-1, DSN-14 F27) ----------


def _first_article(client, created, lot_no="FA-G01") -> dict:
    """계측기를 적을 검사 한 건. 초품이 가장 적은 준비로 만들어진다."""
    _publish_spec(client, created)
    approved = _approved(client, created)
    return _ok(
        _call(
            client,
            created,
            "POST",
            f"/change-notices/{approved['id']}/first-article",
            {"lotNo": lot_no, "lotQty": "10", "unit": "EA", "sampleQty": "3"},
        ),
        201,
    )


def test_gauge_stays_on_the_value_and_reaches_the_certificate(qms):
    """F27·F25. 항목마다 쓴 계측기가 남고, 확정 뒤 성적서가 읽을 수 있다."""
    client, created = qms
    gauge = _gauge(client, created)
    inspection = _first_article(client, created)
    by_name = {v["name"]: v["specItemId"] for v in inspection["values"]}
    saved = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}",
            {
                "values": [
                    {"specItemId": by_name["외관"], "passValue": True},
                    {
                        "specItemId": by_name["핀 피치"],
                        "measuredValue": "2.50",
                        "gaugeId": gauge["id"],
                    },
                ]
            },
        )
    )
    used = {v["name"]: v for v in saved["values"]}
    assert used["핀 피치"]["gaugeId"] == gauge["id"]
    assert used["핀 피치"]["gaugeCode"] == gauge["code"]
    assert used["핀 피치"]["gaugeName"] == gauge["name"]
    # 적지 않은 항목은 빈 채로 둔다 — 눈으로 보는 항목에는 계측기가 없다.
    assert used["외관"]["gaugeId"] is None

    confirmed = _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )
    assert confirmed["result"] == "PASS"
    after = {v["name"]: v for v in confirmed["values"]}
    assert after["핀 피치"]["gaugeCode"] == gauge["code"]


def test_unknown_gauge_is_rejected(qms):
    """다른 공간의 계측기나 지워진 번호는 받지 않는다."""
    client, created = qms
    inspection = _first_article(client, created)
    by_name = {v["name"]: v["specItemId"] for v in inspection["values"]}
    bad = _call(
        client,
        created,
        "PATCH",
        f"/inspections/{inspection['id']}",
        {
            "values": [
                {
                    "specItemId": by_name["핀 피치"],
                    "measuredValue": "2.50",
                    "gaugeId": 999_999,
                }
            ]
        },
    )
    assert bad.status_code == 400
    assert "values.2.gaugeId" in _fields(bad)


def test_overdue_or_repairing_gauge_still_records(qms):
    """설계는 경고까지다(DSN-14 3장). 교정이 지났거나 수리 중이어도 검사를 막지 않는다."""
    client, created = qms
    gauge = _gauge(client, created)
    _ok(_calibrate(client, created, gauge["id"], result="FAIL"), 201)
    assert _ok(client.get(f"{Q}/gauges/{gauge['id']}"))["status"] == "REPAIR"

    inspection = _first_article(client, created)
    by_name = {v["name"]: v["specItemId"] for v in inspection["values"]}
    saved = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}",
            {
                "values": [
                    {
                        "specItemId": by_name["핀 피치"],
                        "measuredValue": "2.50",
                        "gaugeId": gauge["id"],
                    }
                ]
            },
        )
    )
    used = {v["name"]: v for v in saved["values"]}
    assert used["핀 피치"]["gaugeId"] == gauge["id"]
