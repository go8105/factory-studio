"""W2a-1b MES 기준정보: 불량·사유 코드, 근무조·작업자, 라벨 양식, 공정 검사 항목.

핵심 규칙(DSN-12): 불량은 코드로 기록한다(자유 입력 대체). 작업자 코드가 곧 바코드다.
팔레트 라벨만 QR이고 종류마다 기본 양식은 하나다. 수치 검사는 한계와 단위가 있어야 한다.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

SEEDS = ("mes",)  # 공정·품목이 있어야 검사 항목을 만들 수 있다
M = "/api/v1/mes"


@pytest.fixture
def mes(guest_space):
    client, created, _engine = guest_space
    return client, created


def _headers(created, key: str | None = None) -> dict[str, str]:
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": key or str(uuid4()),
    }


def _ok(response, status: int = 200):
    assert response.status_code == status, response.text
    return response.json().get("data") if response.content else None


def _post(client, created, path: str, body: dict):
    return client.post(f"{M}{path}", json=body, headers=_headers(created))


def test_defect_code_is_unique_and_filtered_by_category(mes):
    client, created = mes
    made = _ok(
        _post(
            client,
            created,
            "/defect-codes",
            {"code": "SCR", "name": "긁힘", "category": "APPEARANCE"},
        ),
        201,
    )
    assert made["isActive"] is True  # 등록 본문의 기본값이 저장된다
    again = _post(
        client,
        created,
        "/defect-codes",
        {"code": "SCR", "name": "스크래치", "category": "OTHER"},
    )
    assert again.status_code == 400
    _ok(
        _post(
            client,
            created,
            "/defect-codes",
            {"code": "DIM1", "name": "치수 초과", "category": "DIMENSION"},
        ),
        201,
    )
    appearance = _ok(client.get(f"{M}/defect-codes", params={"category": "APPEARANCE"}))
    assert [row["code"] for row in appearance] == ["SCR"]


def test_planned_stop_belongs_to_downtime_only(mes):
    client, created = mes
    wrong = _post(
        client,
        created,
        "/reason-codes",
        {"category": "SCRAP", "code": "PLAN", "name": "계획 폐기", "planned": True},
    )
    assert wrong.status_code == 400
    assert "planned" in wrong.json()["error"]["details"]["fields"]
    _ok(
        _post(
            client,
            created,
            "/reason-codes",
            {"category": "DOWNTIME", "code": "PM", "name": "예방보전", "planned": True},
        ),
        201,
    )
    # 같은 코드라도 구분이 다르면 쓸 수 있다.
    _ok(
        _post(
            client,
            created,
            "/reason-codes",
            {"category": "SCRAP", "code": "PM", "name": "보전 중 폐기"},
        ),
        201,
    )


def test_worker_code_is_the_barcode_and_shift_must_exist(mes):
    client, created = mes
    shift = _ok(
        _post(
            client,
            created,
            "/shifts",
            {
                "code": "A",
                "name": "주간조",
                "startTime": "08:00:00",
                "endTime": "20:00:00",
            },
        ),
        201,
    )
    missing = _post(
        client,
        created,
        "/workers",
        {"code": "W001", "name": "홍길동", "shiftId": 99999},
    )
    assert missing.status_code == 400
    made = _ok(
        _post(
            client,
            created,
            "/workers",
            {
                "code": "W001",
                "name": "홍길동",
                "shiftId": shift["id"],
                "hrEmployeeCode": "E001",
            },
        ),
        201,
    )
    assert made["hrEmployeeCode"] == "E001"  # HR 사원 코드는 스냅샷이다(FK 아님)
    duplicate = _post(
        client, created, "/workers", {"code": "W001", "name": "다른 사람"}
    )
    assert duplicate.status_code == 400
    # 근무조 없이도 등록된다(교대 미편성).
    _ok(_post(client, created, "/workers", {"code": "W002", "name": "김철수"}), 201)
    by_shift = _ok(client.get(f"{M}/workers", params={"shiftId": shift["id"]}))
    assert [row["code"] for row in by_shift] == ["W001"]


def test_referenced_shift_cannot_be_deleted(mes):
    client, created = mes
    shift = _ok(
        _post(
            client,
            created,
            "/shifts",
            {
                "code": "B",
                "name": "야간조",
                "startTime": "20:00:00",
                "endTime": "08:00:00",
            },
        ),
        201,
    )
    _ok(
        _post(
            client,
            created,
            "/workers",
            {"code": "W010", "name": "이영희", "shiftId": shift["id"]},
        ),
        201,
    )
    blocked = client.delete(f"{M}/shifts/{shift['id']}", headers=_headers(created))
    assert blocked.status_code == 409


def test_pallet_label_uses_qr_and_default_is_one_per_kind(mes):
    client, created = mes

    def make(**body):
        return _post(
            client,
            created,
            "/label-templates",
            {"widthMm": 60, "heightMm": 40, "fields": "lotNo,itemCode,qty", **body},
        )

    wrong = make(code="PAL1", labelKind="PALLET", barcodeType="CODE128")
    assert wrong.status_code == 400
    _ok(make(code="PAL1", labelKind="PALLET", barcodeType="QR", isDefault=True), 201)
    _ok(make(code="LOT1", labelKind="LOT", isDefault=True), 201)
    # 같은 종류의 기본 양식은 하나뿐이다.
    second = make(code="LOT2", labelKind="LOT", isDefault=True)
    assert second.status_code == 400
    assert "isDefault" in second.json()["error"]["details"]["fields"]
    # 기본이 아니면 여러 개 둘 수 있다.
    _ok(make(code="LOT2", labelKind="LOT"), 201)
    # 크기 한계를 벗어나면 막는다.
    assert make(code="BIG", labelKind="BOX", widthMm=300).status_code == 400


def test_range_inspection_needs_limits_and_unit(mes):
    client, created = mes
    process = _ok(client.get(f"{M}/processes"))[0]
    item = _ok(client.get(f"{M}/items"))[0]
    base = {"processId": process["id"], "name": "하우징 높이", "method": "RANGE"}
    assert (
        _post(client, created, "/inspection-items", {**base, "seq": 1}).status_code
        == 400
    )
    no_unit = _post(
        client, created, "/inspection-items", {**base, "seq": 1, "lowerLimit": "9.8"}
    )
    assert no_unit.status_code == 400
    assert "unit" in no_unit.json()["error"]["details"]["fields"]
    flipped = _post(
        client,
        created,
        "/inspection-items",
        {**base, "seq": 1, "lowerLimit": "10.2", "upperLimit": "9.8", "unit": "mm"},
    )
    assert flipped.status_code == 400
    made = _ok(
        _post(
            client,
            created,
            "/inspection-items",
            {**base, "seq": 1, "lowerLimit": "9.8", "upperLimit": "10.2", "unit": "mm"},
        ),
        201,
    )
    assert made["itemId"] is None  # 품목을 비우면 그 공정 공통이다
    # 합·부 검사는 한계를 쓰지 않는다.
    with_limit = _post(
        client,
        created,
        "/inspection-items",
        {
            "processId": process["id"],
            "seq": 2,
            "name": "외관",
            "method": "PASS_FAIL",
            "unit": "mm",
        },
    )
    assert with_limit.status_code == 400
    _ok(
        _post(
            client,
            created,
            "/inspection-items",
            {
                "processId": process["id"],
                "seq": 2,
                "name": "외관",
                "method": "PASS_FAIL",
            },
        ),
        201,
    )
    # 공정·품목이 같으면 순번은 유일하다.
    assert (
        _post(
            client,
            created,
            "/inspection-items",
            {
                "processId": process["id"],
                "seq": 2,
                "name": "다른 항목",
                "method": "PASS_FAIL",
            },
        ).status_code
        == 400
    )
    # 품목을 지정하면 그 품목 전용이라 같은 순번을 다시 쓸 수 있다.
    _ok(
        _post(
            client,
            created,
            "/inspection-items",
            {
                "processId": process["id"],
                "itemId": item["id"],
                "seq": 2,
                "name": "품목 전용 점검",
                "method": "PASS_FAIL",
            },
        ),
        201,
    )
    mine = _ok(client.get(f"{M}/inspection-items", params={"itemId": item["id"]}))
    assert [row["name"] for row in mine] == ["품목 전용 점검"]
