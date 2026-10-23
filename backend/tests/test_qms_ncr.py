"""QMS-1d: 부적합 보고(Q-07)와 시정·예방 조치(Q-08) — DSN-14 F31·F32.

부적합은 발생처마다 근거가 다르다(수입·출하는 불합격 검사, 공정은 MES 불량, 고객은 클레임).
조치는 부적합에 속하고, **연결 조치를 모두 유효성 확인해야 부적합이 종결된다**(DB_POLICY Q3).
"""

from itertools import count

import pytest
from sqlalchemy import text

Q = "/api/v1/qms"
_keys = count()
TODAY = "2026-09-24"  # guest_space fixture의 FS_TODAY

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


@pytest.fixture
def qms(guest_space):
    client, created, engine = guest_space
    with engine.begin() as connection:
        for table in (
            "capa",
            "ncr",
            "quality_hold",
            "inspection_value",
            "inspection",
            "inspection_spec_item",
            "inspection_spec",
            "defect_type",
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


def _failed_inspection(client, created) -> dict:
    """불합격 확정 검사 1건. 출하 발생처 부적합의 근거가 된다."""
    lots = _ok(client.get(f"{Q}/lookups/mes-lots"))
    lot = lots[0]
    spec = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspection-specs",
            {
                "itemCode": lot["itemCode"],
                "itemName": lot["itemName"],
                "items": SPEC_ITEMS,
            },
        ),
        201,
    )
    _ok(_call(client, created, "POST", f"/inspection-specs/{spec['id']}/publish"))
    defect = _ok(
        _call(
            client,
            created,
            "POST",
            "/defect-types",
            {"code": "DIMENSION", "name": "치수 불량"},
        ),
        201,
    )
    inspection = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections",
            {"source": "MES", "lotNo": lot["lotNo"], "sampleQty": "3"},
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
                    {
                        "specItemId": by_name["핀 피치"],
                        "measuredValue": "2.60",
                        "defectTypeId": defect["id"],
                    },
                ]
            },
        )
    )
    confirmed = _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )
    assert confirmed["result"] == "FAIL"
    return confirmed


def _ncr(client, created, **extra) -> dict:
    body = {
        "origin": "PROCESS",
        "itemCode": "FG-C100",
        "qty": "12",
        "description": "핀 피치가 상한을 벗어났습니다.",
        **extra,
    }
    return _ok(_call(client, created, "POST", "/ncrs", body), 201)


def _capa(client, created, ncr_id: int, **extra) -> dict:
    body = {
        "ncrId": ncr_id,
        "kind": "CORRECTIVE",
        "rootCause": "금형 마모",
        "action": "금형 교체 후 초품 확인",
        "ownerName": "김정비",
        "dueOn": "2026-10-10",
        **extra,
    }
    return _ok(_call(client, created, "POST", "/capas", body), 201)


# ---------- 부적합 보고 (Q-07) ----------


def test_process_ncr_needs_no_inspection(qms):
    """공정 부적합은 근거 검사 없이 직접 적을 수 있다 — MES를 꺼도 기록은 성립한다."""
    client, created = qms
    ncr = _ncr(client, created)
    assert ncr["status"] == "OPEN" and ncr["ncrNo"].startswith("NCR-20260924-")
    assert ncr["reportedOn"] == TODAY
    assert ncr["capaCount"] == 0 and ncr["verifiedCount"] == 0


def test_outgoing_ncr_requires_a_failed_inspection(qms):
    """수입·출하 부적합의 근거는 확정·불합격한 검사다(DB CHECK와 같은 규칙)."""
    client, created = qms
    missing = _call(
        client,
        created,
        "POST",
        "/ncrs",
        {
            "origin": "OUTGOING",
            "itemCode": "FG-C100",
            "qty": "5",
            "description": "출하 검사 불합격",
        },
    )
    assert missing.status_code == 400 and "inspectionId" in _fields(missing)

    confirmed = _failed_inspection(client, created)
    ncr = _ncr(
        client,
        created,
        origin="OUTGOING",
        itemCode=confirmed["itemCode"],
        lotNo=confirmed["lotNo"],
        inspectionId=confirmed["id"],
    )
    assert ncr["inspectionNo"] == confirmed["inspectionNo"]


def test_process_ncr_rejects_an_inspection_reference(qms):
    """발생처에 맞지 않는 근거는 받지 않는다."""
    client, created = qms
    confirmed = _failed_inspection(client, created)
    response = _call(
        client,
        created,
        "POST",
        "/ncrs",
        {
            "origin": "PROCESS",
            "itemCode": "FG-C100",
            "qty": "5",
            "description": "공정 불량",
            "inspectionId": confirmed["id"],
        },
    )
    assert response.status_code == 400 and "inspectionId" in _fields(response)


def test_customer_ncr_is_not_made_here(qms):
    """고객 발생 부적합은 클레임에서 만든다(Q-09, 1e)."""
    client, created = qms
    response = _call(
        client,
        created,
        "POST",
        "/ncrs",
        {
            "origin": "CUSTOMER",
            "itemCode": "FG-C100",
            "qty": "5",
            "description": "고객 불만",
        },
    )
    assert response.status_code == 409 and _reason(response) == "CLAIM_REQUIRED"


def test_one_ncr_per_source(qms):
    """같은 원천으로 두 번 보고하지 않는다(UK_PARTIAL)."""
    client, created = qms
    _ncr(client, created, sourceRef="LT-0013:INJ")
    again = _call(
        client,
        created,
        "POST",
        "/ncrs",
        {
            "origin": "PROCESS",
            "itemCode": "FG-C100",
            "qty": "3",
            "description": "같은 원천",
            "sourceRef": "LT-0013:INJ",
        },
    )
    assert again.status_code == 400 and "sourceRef" in _fields(again)


def test_process_sources_come_from_mes_and_drop_the_used_ones(qms):
    """공정 근거 후보는 MES 불량이다. 이미 보고한 원천은 목록에서 빠진다."""
    client, created = qms
    month = "2026-09"
    first = _ok(client.get(f"{Q}/ncrs/sources?origin=PROCESS&month={month}"))
    assert first["mesEnabled"] is True
    if not first["rows"]:
        pytest.skip("시드에 그 달 공정 불량이 없다")
    ref = first["rows"][0]["sourceRef"]
    _ncr(client, created, sourceRef=ref)
    again = _ok(client.get(f"{Q}/ncrs/sources?origin=PROCESS&month={month}"))
    assert ref not in {r["sourceRef"] for r in again["rows"]}


def test_outgoing_sources_are_failed_inspections_not_yet_reported(qms):
    client, created = qms
    confirmed = _failed_inspection(client, created)
    before = _ok(client.get(f"{Q}/ncrs/sources?origin=OUTGOING"))
    assert confirmed["id"] in {r["id"] for r in before["rows"]}
    _ncr(
        client,
        created,
        origin="OUTGOING",
        itemCode=confirmed["itemCode"],
        inspectionId=confirmed["id"],
    )
    after = _ok(client.get(f"{Q}/ncrs/sources?origin=OUTGOING"))
    assert confirmed["id"] not in {r["id"] for r in after["rows"]}


# ---------- 시정·예방 조치 (Q-08) ----------


def test_capa_runs_open_done_verified(qms):
    """조치는 완료한 뒤에만 확인한다. 확인에는 내용이 필요하다."""
    client, created = qms
    ncr = _ncr(client, created)
    capa = _capa(client, created, ncr["id"])
    assert capa["status"] == "OPEN" and capa["capaNo"].startswith("CA-20260924-")
    assert capa["ncrNo"] == ncr["ncrNo"]

    early = _call(
        client,
        created,
        "POST",
        f"/capas/{capa['id']}/verification",
        {"effective": True, "note": "확인"},
    )
    assert early.status_code == 409 and _reason(early) == "CAPA_NOT_DONE"

    done = _ok(_call(client, created, "POST", f"/capas/{capa['id']}/completion"))
    assert done["status"] == "DONE" and done["doneAt"]

    verified = _ok(
        _call(
            client,
            created,
            "POST",
            f"/capas/{capa['id']}/verification",
            {"effective": True, "note": "3개월 재발 없음"},
        )
    )
    assert verified["status"] == "VERIFIED"
    assert verified["verifiedAt"] >= verified["doneAt"]


def test_completed_capa_is_no_longer_editable(qms):
    client, created = qms
    ncr = _ncr(client, created)
    capa = _capa(client, created, ncr["id"])
    _ok(_call(client, created, "POST", f"/capas/{capa['id']}/completion"))
    response = _call(
        client, created, "PATCH", f"/capas/{capa['id']}", {"action": "다시 씁니다"}
    )
    assert response.status_code == 409 and _reason(response) == "CAPA_NOT_OPEN"


def test_ineffective_capa_does_not_close_the_ncr(qms):
    """무효 판정은 되돌리지 않는다 — 새 조치를 만들어 다시 확인한다."""
    client, created = qms
    ncr = _ncr(client, created)
    capa = _capa(client, created, ncr["id"])
    _ok(_call(client, created, "POST", f"/capas/{capa['id']}/completion"))
    bad = _ok(
        _call(
            client,
            created,
            "POST",
            f"/capas/{capa['id']}/verification",
            {"effective": False, "note": "같은 불량이 재발했습니다"},
        )
    )
    assert bad["status"] == "INEFFECTIVE"
    blocked = _call(client, created, "POST", f"/ncrs/{ncr['id']}/closure")
    assert blocked.status_code == 409 and _reason(blocked) == "CAPA_NOT_VERIFIED"


def test_ncr_closes_only_when_every_capa_is_verified(qms):
    client, created = qms
    ncr = _ncr(client, created)
    empty = _call(client, created, "POST", f"/ncrs/{ncr['id']}/closure")
    assert empty.status_code == 409 and _reason(empty) == "NO_CAPA"

    first = _capa(client, created, ncr["id"])
    second = _capa(client, created, ncr["id"], kind="PREVENTIVE")
    for capa in (first, second):
        _ok(_call(client, created, "POST", f"/capas/{capa['id']}/completion"))
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/capas/{first['id']}/verification",
            {"effective": True, "note": "유효"},
        )
    )
    partial = _call(client, created, "POST", f"/ncrs/{ncr['id']}/closure")
    assert partial.status_code == 409
    assert partial.json()["error"]["details"]["open"] == 1

    _ok(
        _call(
            client,
            created,
            "POST",
            f"/capas/{second['id']}/verification",
            {"effective": True, "note": "유효"},
        )
    )
    closed = _ok(_call(client, created, "POST", f"/ncrs/{ncr['id']}/closure"))
    assert closed["status"] == "CLOSED" and closed["closedAt"]


def test_closed_ncr_takes_no_edit_and_no_new_capa(qms):
    client, created = qms
    ncr = _ncr(client, created)
    capa = _capa(client, created, ncr["id"])
    _ok(_call(client, created, "POST", f"/capas/{capa['id']}/completion"))
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/capas/{capa['id']}/verification",
            {"effective": True, "note": "유효"},
        )
    )
    _ok(_call(client, created, "POST", f"/ncrs/{ncr['id']}/closure"))

    edit = _call(
        client, created, "PATCH", f"/ncrs/{ncr['id']}", {"description": "고쳐 봅니다"}
    )
    assert edit.status_code == 409 and _reason(edit) == "NCR_CLOSED"
    more = _call(
        client,
        created,
        "POST",
        "/capas",
        {
            "ncrId": ncr["id"],
            "kind": "PREVENTIVE",
            "rootCause": "추가",
            "action": "추가",
            "ownerName": "담당",
            "dueOn": "2026-10-10",
        },
    )
    assert more.status_code == 409 and _reason(more) == "NCR_CLOSED"
