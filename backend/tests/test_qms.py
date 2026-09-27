"""FS-023b QMS API (AC-97~110). 검증 항목마다 테스트를 나눈다.

`qms` fixture는 게스트 공간의 QMS 시드(FS-023c)를 지우고 빈 QMS에서 시작한다. 기준·검사는 테스트가 API로 만든다.
MES 시드의 정상 완료 LOT(패킹 대상 2건 등)을 읽기 전용 조회로 검사한다(D9).
시드 자체는 `seeded` fixture로 따로 검사한다(파일 끝).
"""

from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import text

Q = "/api/v1/qms"
_keys = count()


QMS_TABLES = (
    "quality_hold",
    "inspection_value",
    "inspection",
    "inspection_spec_item",
    "inspection_spec",
    "defect_type",
)


@pytest.fixture
def seeded(guest_space):
    return guest_space[:2]


@pytest.fixture
def qms(guest_space):
    client, created, engine = guest_space
    with engine.begin() as connection:
        for table in QMS_TABLES:
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
        path if path.startswith("/api") else f"{Q}{path}",
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


ITEMS = [
    {"name": "외관", "method": "PASS_FAIL"},
    {
        "name": "핀 피치",
        "method": "RANGE",
        "lowerLimit": "2.48",
        "upperLimit": "2.52",
        "unit": "mm",
    },
    {
        "name": "절연 저항",
        "method": "RANGE",
        "lowerLimit": "100",
        "unit": "MΩ",
        "isRequired": False,
    },
]


def _lot(client, created) -> dict:
    """검사 대기 LOT 1건(MES 조회)."""
    lots = _ok(client.get(f"{Q}/lookups/mes-lots"))
    assert lots, "시드에 정상 완료 LOT이 있어야 한다"
    return lots[0]


def _published_spec(client, created, item_code: str, name="품목") -> dict:
    spec = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspection-specs",
            {"itemCode": item_code, "itemName": name, "items": ITEMS},
        ),
        201,
    )
    return _ok(
        _call(client, created, "POST", f"/inspection-specs/{spec['id']}/publish")
    )


def _defect(client, created, code="DIMENSION") -> dict:
    return _ok(
        _call(
            client,
            created,
            "POST",
            "/defect-types",
            {"code": code, "name": "치수 불량"},
        ),
        201,
    )


def _inspection(client, created, lot: dict, sample="10") -> dict:
    return _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections",
            {"source": "MES", "lotNo": lot["lotNo"], "sampleQty": sample},
        ),
        201,
    )


def _values(
    inspection: dict, pitch: str, appearance=True, defect=None, insulation=None
) -> list[dict]:
    by_name = {v["name"]: v["specItemId"] for v in inspection["values"]}
    values = [
        {"specItemId": by_name["외관"], "passValue": appearance},
        {
            "specItemId": by_name["핀 피치"],
            "measuredValue": pitch,
            "defectTypeId": defect,
        },
    ]
    if insulation is not None:
        values.append({"specItemId": by_name["절연 저항"], "measuredValue": insulation})
    return values


def _failed(client, created, lot=None) -> tuple[dict, dict, dict]:
    """불합격 확정 검사와 그 보류를 만든다."""
    lot = lot or _lot(client, created)
    _published_spec(client, created, lot["itemCode"])
    defect = _defect(client, created)
    inspection = _inspection(client, created, lot)
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}",
            {"values": _values(inspection, "2.60", defect=defect["id"])},
        )
    )
    confirmed = _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )
    return lot, confirmed, defect


def test_guest_has_qms_module(qms):
    client, _ = qms
    modules = {
        m["moduleKey"]: m["enabled"]
        for m in client.get("/api/v1/core/workspace/modules").json()["data"]
    }
    assert modules["qms"] is True


def test_published_spec_items_are_immutable(qms):
    """AC-97"""
    client, created = qms
    spec = _published_spec(client, created, "FG-C100")
    response = _call(
        client,
        created,
        "PATCH",
        f"/inspection-specs/{spec['id']}",
        {"items": ITEMS[:1]},
    )
    assert response.status_code == 409 and _reason(response) == "PUBLISHED_IMMUTABLE"
    assert len(_ok(client.get(f"{Q}/inspection-specs/{spec['id']}"))["items"]) == 3


def test_new_version_retires_previous_publication(qms):
    """AC-98"""
    client, created = qms
    first = _published_spec(client, created, "FG-C100")
    draft = _ok(
        _call(client, created, "POST", f"/inspection-specs/{first['id']}/revise"), 201
    )
    assert (
        draft["versionNo"] == 2
        and draft["status"] == "draft"
        and len(draft["items"]) == 3
    )
    _ok(_call(client, created, "POST", f"/inspection-specs/{draft['id']}/publish"))
    specs = _ok(client.get(f"{Q}/inspection-specs?itemCode=FG-C100"))
    assert [(s["versionNo"], s["status"]) for s in specs] == [
        (2, "published"),
        (1, "retired"),
    ]


def test_spec_item_rules_are_field_errors(qms):
    client, created = qms
    response = _call(
        client,
        created,
        "POST",
        "/inspection-specs",
        {
            "itemCode": "FG-C100",
            "itemName": "커넥터",
            "items": [
                {
                    "name": "치수",
                    "method": "RANGE",
                    "lowerLimit": "5",
                    "upperLimit": "1",
                }
            ],
        },
    )
    assert response.status_code == 400
    fields = response.json()["error"]["details"]["fields"]
    assert set(fields) == {"items.0.unit", "items.0.upperLimit"}


def test_publish_requires_items(qms):
    client, created = qms
    spec = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspection-specs",
            {"itemCode": "FG-C100", "itemName": "커넥터"},
        ),
        201,
    )
    response = _call(client, created, "POST", f"/inspection-specs/{spec['id']}/publish")
    assert response.status_code == 409 and _reason(response) == "NO_ITEMS"


def test_lookup_reads_completed_mes_lots(qms):
    """D9: MES 정상 완료 LOT을 읽어 온다. 기준이 없으면 hasSpec=false."""
    client, _ = qms
    lots = _ok(client.get(f"{Q}/lookups/mes-lots"))
    assert lots and all(Decimal(lot["finalGoodQty"]) > 0 for lot in lots)
    assert all(lot["status"] == "pending" and lot["hasSpec"] is False for lot in lots)
    mes_lot = next(
        x
        for x in client.get("/api/v1/mes/lots").json()["data"]
        if x["lotNo"] == lots[0]["lotNo"]
    )
    assert mes_lot["status"] == "completed"


def test_inspection_copies_mes_snapshot_and_fixes_spec(qms):
    """D11·AC-99: 스냅샷 복사, 개정해도 만든 검사의 기준은 그대로."""
    client, created = qms
    lot = _lot(client, created)
    spec = _published_spec(client, created, lot["itemCode"])
    inspection = _inspection(client, created, lot)
    assert (inspection["lotQty"], inspection["itemCode"], inspection["source"]) == (
        lot["finalGoodQty"],
        lot["itemCode"],
        "MES",
    )
    assert inspection["inspectionNo"].startswith("QI-20260924-")
    revised = _ok(
        _call(client, created, "POST", f"/inspection-specs/{spec['id']}/revise"), 201
    )
    _ok(_call(client, created, "POST", f"/inspection-specs/{revised['id']}/publish"))
    assert (
        _ok(client.get(f"{Q}/inspections/{inspection['id']}"))["specId"] == spec["id"]
    )
    assert _ok(client.get(f"{Q}/lookups/mes-lots"))[0]["status"] == "drafting"


def test_server_judges_range_items(qms):
    """AC-100: 경계값은 합격, 상한 초과는 불합격. 판정은 서버가 계산한다."""
    client, created = qms
    lot = _lot(client, created)
    _published_spec(client, created, lot["itemCode"])
    inspection = _inspection(client, created, lot)
    updated = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}",
            {"values": _values(inspection, "2.52", insulation="99")},
        )
    )
    judged = {v["name"]: v["judgement"] for v in updated["values"]}
    assert judged == {"외관": "PASS", "핀 피치": "PASS", "절연 저항": "FAIL"}


def test_missing_required_value_blocks_confirmation(qms):
    """AC-101"""
    client, created = qms
    lot = _lot(client, created)
    _published_spec(client, created, lot["itemCode"])
    inspection = _inspection(client, created, lot)
    response = _call(
        client, created, "POST", f"/inspections/{inspection['id']}/confirm"
    )
    assert response.status_code == 400
    assert set(response.json()["error"]["details"]["fields"]) == {
        "values.1",
        "values.2",
    }


def test_failed_item_needs_defect_type(qms):
    client, created = qms
    lot = _lot(client, created)
    _published_spec(client, created, lot["itemCode"])
    inspection = _inspection(client, created, lot)
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}",
            {"values": _values(inspection, "2.60")},
        )
    )
    response = _call(
        client, created, "POST", f"/inspections/{inspection['id']}/confirm"
    )
    assert response.status_code == 400
    assert "values.2.defectTypeId" in response.json()["error"]["details"]["fields"]


def test_failed_confirmation_creates_hold(qms):
    """AC-102: 불합격 확정과 같은 트랜잭션에서 보류가 생긴다."""
    client, created = qms
    lot, confirmed, _ = _failed(client, created)
    assert confirmed["result"] == "FAIL"
    assert confirmed["activeHold"]["lotNo"] == lot["lotNo"]
    assert confirmed["activeHold"]["holdNo"].startswith("QH-20260924-")
    holds = _ok(client.get(f"{Q}/holds?status=held"))
    assert [h["lotNo"] for h in holds] == [lot["lotNo"]]


def test_second_failure_keeps_single_active_hold(qms):
    """AC-103(순차 경로): 같은 LOT이 다시 불합격이어도 활성 보류는 1건이다."""
    client, created = qms
    _, confirmed, defect = _failed(client, created)
    again = _ok(
        _call(client, created, "POST", f"/inspections/{confirmed['id']}/reinspect"), 201
    )
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{again['id']}",
            {"values": _values(again, "2.70", defect=defect["id"])},
        )
    )
    second = _ok(_call(client, created, "POST", f"/inspections/{again['id']}/confirm"))
    assert second["result"] == "FAIL"
    assert second["activeHold"]["id"] == confirmed["activeHold"]["id"]
    assert len(_ok(client.get(f"{Q}/holds?status=held"))) == 1


def test_confirmed_inspection_is_immutable(qms):
    """AC-104(검사)"""
    client, created = qms
    _, confirmed, _ = _failed(client, created)
    for method, body in (("PATCH", {"note": "변경"}), ("DELETE", None)):
        response = _call(
            client, created, method, f"/inspections/{confirmed['id']}", body
        )
        assert (
            response.status_code == 409 and _reason(response) == "CONFIRMED_IMMUTABLE"
        )


def test_reinspection_pass_releases_hold(qms):
    """AC-105: 합격 재검사 전에는 REINSPECTED 해제 불가, 합격 뒤에는 가능. 해제 뒤 불변(AC-104)."""
    client, created = qms
    _, confirmed, _ = _failed(client, created)
    hold_id = confirmed["activeHold"]["id"]
    blocked = _call(
        client,
        created,
        "POST",
        f"/holds/{hold_id}/release",
        {"disposition": "REINSPECTED", "releaseInspectionId": confirmed["id"]},
    )
    assert blocked.status_code == 409 and _reason(blocked) == "RELEASE_NOT_ALLOWED"
    again = _ok(
        _call(client, created, "POST", f"/inspections/{confirmed['id']}/reinspect"), 201
    )
    assert again["reinspectionOfId"] == confirmed["id"]
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{again['id']}",
            {"values": _values(again, "2.50")},
        )
    )
    passed = _ok(_call(client, created, "POST", f"/inspections/{again['id']}/confirm"))
    assert passed["result"] == "PASS" and passed["activeHold"]["id"] == hold_id
    released = _ok(
        _call(
            client,
            created,
            "POST",
            f"/holds/{hold_id}/release",
            {"disposition": "REINSPECTED", "releaseInspectionId": again["id"]},
        )
    )
    assert (
        released["status"],
        released["disposition"],
        released["releaseInspectionNo"],
    ) == ("released", "REINSPECTED", again["inspectionNo"])
    twice = _call(
        client,
        created,
        "POST",
        f"/holds/{hold_id}/release",
        {"disposition": "SCRAP", "reason": "다시"},
    )
    assert twice.status_code == 409 and _reason(twice) == "ALREADY_RELEASED"


def test_concession_requires_reason(qms):
    """AC-106"""
    client, created = qms
    _, confirmed, _ = _failed(client, created)
    hold_id = confirmed["activeHold"]["id"]
    missing = _call(
        client,
        created,
        "POST",
        f"/holds/{hold_id}/release",
        {"disposition": "CONCESSION"},
    )
    assert (
        missing.status_code == 400
        and "reason" in missing.json()["error"]["details"]["fields"]
    )
    released = _ok(
        _call(
            client,
            created,
            "POST",
            f"/holds/{hold_id}/release",
            {"disposition": "CONCESSION", "reason": "고객 승인 특채"},
        )
    )
    assert released["releaseReason"] == "고객 승인 특채"


def test_mes_off_falls_back_to_manual_entry(qms):
    """AC-107: MES를 끄면 조회는 SOURCE_MODULE_DISABLED, 직접 입력 검사는 된다."""
    client, created = qms
    _published_spec(client, created, "FG-C100")
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/mes",
            {"enabled": False},
        )
    )
    lookup = client.get(f"{Q}/lookups/mes-lots")
    assert lookup.status_code == 409 and _reason(lookup) == "SOURCE_MODULE_DISABLED"
    from_mes = _call(
        client,
        created,
        "POST",
        "/inspections",
        {"source": "MES", "lotNo": "LT-0016", "sampleQty": "5"},
    )
    assert from_mes.status_code == 409 and _reason(from_mes) == "SOURCE_MODULE_DISABLED"
    manual = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections",
            {
                "source": "MANUAL",
                "lotNo": "EXT-001",
                "sampleQty": "5",
                "itemCode": "FG-C100",
                "itemName": "커넥터",
                "lotQty": "100",
                "unit": "EA",
            },
        ),
        201,
    )
    assert (manual["source"], manual["lotQty"]) == ("MANUAL", "100.000")
    assert _ok(client.get(f"{Q}/dashboard"))["pendingLots"] is None


def test_qms_off_leaves_mes_unchanged(qms):
    """AC-108: QMS를 끄면 MES는 그대로이고 qualityHold는 null이다. QMS API는 MODULE_DISABLED."""
    client, created = qms
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/qms",
            {"enabled": False},
        )
    )
    lots = client.get("/api/v1/mes/lots").json()["data"]
    assert lots and all(lot["qualityHold"] is None for lot in lots)
    detail = client.get(f"/api/v1/mes/lots/{lots[0]['id']}").json()["data"]
    assert detail["qualityHold"] is None and detail["qualityResult"] is None
    assert (
        client.get(f"{Q}/holds").json()["error"]["details"]["reason"]
        == "MODULE_DISABLED"
    )


def test_held_lot_is_badged_but_still_packable(qms):
    """AC-109: 보류 LOT은 패킹 대기에 배지(qualityHold=true)로 보이고, 담을 수 있다(D10)."""
    client, created = qms
    packable = {
        x["lotNo"]: x for x in client.get("/api/v1/mes/packable-lots").json()["data"]
    }
    lot = next(
        x for x in _ok(client.get(f"{Q}/lookups/mes-lots")) if x["lotNo"] in packable
    )
    _failed(client, created, lot)
    target = next(
        x
        for x in client.get("/api/v1/mes/packable-lots").json()["data"]
        if x["lotNo"] == lot["lotNo"]
    )
    assert target["qualityHold"] is True
    box = _ok(
        _call(
            client, created, "POST", "/api/v1/mes/packing-units", {"packingKind": "BOX"}
        ),
        201,
    )
    packed = _call(
        client,
        created,
        "PUT",
        f"/api/v1/mes/packing-units/{box['id']}/members",
        {"lotId": target["lotId"], "packedQty": "1"},
    )
    assert packed.status_code == 200, packed.text
    mes_lot = next(
        x
        for x in client.get("/api/v1/mes/lots").json()["data"]
        if x["lotNo"] == lot["lotNo"]
    )
    assert mes_lot["qualityHold"] is True
    detail = client.get(f"/api/v1/mes/lots/{mes_lot['id']}").json()["data"]
    assert detail["qualityResult"] == "FAIL"


def test_other_workspace_cannot_see_inspection(qms, guest_space):
    """AC-110: 다른 공간의 검사는 404."""
    client, created = qms
    _, confirmed, _ = _failed(client, created)
    from uuid import uuid4

    from fastapi.testclient import TestClient

    other = TestClient(client.app, base_url="https://testserver")
    assert (
        other.post(
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 201
    )
    assert other.get(f"{Q}/inspections/{confirmed['id']}").status_code == 404
    # 다른 공간에는 그 공간의 시드 보류만 보인다.
    held = other.get(f"{Q}/holds?status=held").json()["data"]
    assert confirmed["id"] not in {h["inspectionId"] for h in held}


def test_defect_type_in_use_cannot_be_deleted(qms):
    client, created = qms
    _, _, defect = _failed(client, created)
    response = _call(client, created, "DELETE", f"/defect-types/{defect['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["references"][0]["count"] == 1
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/defect-types/{defect['id']}",
            {"isActive": False},
        )
    )


def test_dashboard_counts_confirmed_month(qms):
    client, created = qms
    _failed(client, created)
    data = _ok(client.get(f"{Q}/dashboard"))
    assert (
        data["month"],
        data["inspected"],
        data["passRate"],
        data["activeHolds"],
    ) == ("2026-09", 1, "0.0", 1)
    assert data["topDefects"][0]["code"] == "DIMENSION"
    assert data["pendingLots"] is not None


def test_seed_demo_flow(seeded):
    """FS-023c 시드: 대기·작성 중·보류 LOT이 보이고, 시드 재검사로 보류를 해제할 수 있다."""
    client, created = seeded
    lots = {x["lotNo"]: x for x in _ok(client.get(f"{Q}/lookups/mes-lots"))}
    assert {k: (v["status"], v["hasSpec"]) for k, v in lots.items()} == {
        "LT-0015": ("drafting", True),
        "LT-0017": ("pending", True),
    }
    inspections = _ok(client.get(f"{Q}/inspections"))
    assert len(inspections) == 17
    # 번호 속 날짜는 복사 후에도 검사일과 같다.
    assert all(
        i["inspectionNo"][3:11] == i["inspectedOn"].replace("-", "")
        and i["inspectionMonth"] == i["inspectedOn"][:7]
        for i in inspections
    )
    held = _ok(client.get(f"{Q}/holds?status=held"))
    assert [h["lotNo"] for h in held] == ["LT-0016"]
    packable = {
        x["lotNo"]: x for x in client.get("/api/v1/mes/packable-lots").json()["data"]
    }
    assert packable["LT-0016"]["qualityHold"] is True
    assert _ok(client.get(f"{Q}/dashboard"))["activeHolds"] == 1

    retest = next(i for i in inspections if i["reinspectionOfId"])
    detail = _ok(client.get(f"{Q}/inspections/{retest['id']}"))
    by_name = {v["name"]: v["specItemId"] for v in detail["values"]}
    values = [
        {"specItemId": by_name["외관"], "passValue": True},
        {"specItemId": by_name["핀 피치"], "measuredValue": "2.54"},
        {"specItemId": by_name["하우징 높이"], "measuredValue": "9.00"},
        {"specItemId": by_name["절연 저항"], "measuredValue": "300"},
    ]
    _ok(
        _call(
            client, created, "PATCH", f"/inspections/{retest['id']}", {"values": values}
        )
    )
    passed = _ok(_call(client, created, "POST", f"/inspections/{retest['id']}/confirm"))
    assert passed["result"] == "PASS"
    released = _ok(
        _call(
            client,
            created,
            "POST",
            f"/holds/{held[0]['id']}/release",
            {"disposition": "REINSPECTED", "releaseInspectionId": retest["id"]},
        )
    )
    assert released["status"] == "released"
