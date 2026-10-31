"""QMS-1g-2: 품질 지표(Q-13)와 대시보드 미결 카드(Q-01) — DSN-14 F72·F71.

지표는 저장하지 않고 조회할 때마다 센다. **PPM은 불량 개수를 적는 검사에서만** 낸다 —
출하 검사와 클레임에는 개수 칸이 없어 LOT 불합격률·건수까지만 낸다. 0으로 채우지 않는다.
"""

from itertools import count

import pytest
from sqlalchemy import text

Q = "/api/v1/qms"
_keys = count()
TODAY = "2026-09-24"  # guest_space fixture의 FS_TODAY
MONTH = "2026-09"

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
            "claim",
            "calibration",
            "gauge",
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
            "Idempotency-Key": f"m{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _published_spec(client, created, item_code="FG-C100") -> dict:
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


def _outgoing(client, created, lot_no: str, pitch: str) -> dict:
    """직접 입력 출하 검사 한 건을 만들어 확정한다. 불합격이면 불량 유형을 함께 고른다."""
    inspection = _ok(
        _call(
            client,
            created,
            "POST",
            "/inspections",
            {
                "source": "MANUAL",
                "lotNo": lot_no,
                "itemCode": "FG-C100",
                "itemName": "완제품",
                "lotQty": "100",
                "unit": "EA",
                "sampleQty": "5",
            },
        ),
        201,
    )
    by_name = {v["name"]: v["specItemId"] for v in inspection["values"]}
    defect = _ok(
        _call(
            client,
            created,
            "POST",
            "/defect-types",
            {"code": f"D{lot_no.replace('-', '')}", "name": "치수 이탈"},
        ),
        201,
    )
    values = [
        {"specItemId": by_name["외관"], "passValue": True},
        {"specItemId": by_name["핀 피치"], "measuredValue": pitch},
    ]
    if not ("2.48" <= pitch <= "2.52"):
        values[1]["defectTypeId"] = defect["id"]
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/inspections/{inspection['id']}",
            {"values": values},
        )
    )
    return _ok(
        _call(client, created, "POST", f"/inspections/{inspection['id']}/confirm")
    )


def test_metrics_are_empty_without_inspections(qms):
    """검사가 없으면 0%가 아니라 '낼 수 없음'이다. 검사 안 한 것과 다 합격한 것은 다르다."""
    client, _ = qms
    data = _ok(client.get(f"{Q}/metrics"))
    assert data["outgoing"] == {
        "lots": 0,
        "failedLots": 0,
        "failRate": None,
        "ppm": None,
    }
    assert data["pareto"] == []
    assert data["trend"] == []
    assert data["months"] == []


def test_outgoing_gets_a_fail_rate_but_no_ppm(qms):
    """출하 검사에는 불량 '개수' 칸이 없다. 불합격률까지만 내고 PPM은 비운다."""
    client, created = qms
    _published_spec(client, created)
    _outgoing(client, created, "LT-1", "2.50")
    fail = _outgoing(client, created, "LT-2", "2.60")
    assert fail["result"] == "FAIL"

    data = _ok(client.get(f"{Q}/metrics?month={MONTH}"))
    assert data["outgoing"]["lots"] == 2
    assert data["outgoing"]["failedLots"] == 1
    assert data["outgoing"]["failRate"] == "50.0"
    assert data["outgoing"]["ppm"] is None, "출하에는 PPM을 내지 않는다"
    assert data["customer"] == {"claims": 0, "qty": "0"}


def test_pareto_counts_the_defect_types_that_were_chosen(qms):
    client, created = qms
    _published_spec(client, created)
    _outgoing(client, created, "LT-3", "2.60")
    data = _ok(client.get(f"{Q}/metrics?month={MONTH}"))
    assert [(r["code"], r["count"]) for r in data["pareto"]] == [("DLT3", 1)]


def test_trend_holds_one_row_per_month(qms):
    client, created = qms
    _published_spec(client, created)
    _outgoing(client, created, "LT-4", "2.50")
    data = _ok(client.get(f"{Q}/metrics?month={MONTH}"))
    assert len(data["trend"]) == 1
    row = data["trend"][0]
    assert row["month"] == MONTH and row["inspected"] == 1 and row["failed"] == 0
    assert row["ppm"] is None, "불량 개수를 적지 않은 달은 PPM이 없다"
    assert data["months"] == [MONTH]


def test_process_is_unknown_when_mes_is_off(qms, guest_space):
    """MES를 끄면 공정은 0이 아니라 null이다 — 화면이 '읽지 않습니다'로 말한다."""
    client, created = qms
    engine = guest_space[2]
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false "
                "WHERE workspace_id=:w AND module_key='mes'"
            ),
            {"w": created["workspaceId"]},
        )
    data = _ok(client.get(f"{Q}/metrics?month={MONTH}"))
    assert data["process"] is None
    assert data["processPareto"] is None


def test_dashboard_counts_open_work(qms):
    """F71. 미결 NCR·CAPA·클레임·교정 도래를 센다."""
    client, created = qms
    before = _ok(client.get(f"{Q}/dashboard"))
    assert before["openNcrs"] == 0 and before["openCapas"] == 0
    assert before["openClaims"] == 0 and before["gaugesDue"] == 0

    claim = _ok(
        _call(
            client,
            created,
            "POST",
            "/claims",
            {
                "customerCode": "C-001",
                "receivedOn": TODAY,
                "itemCode": "FG-C100",
                "qty": "3",
                "severity": "MINOR",
                "description": "포장 파손",
            },
        ),
        201,
    )
    assert claim["status"] == "RECEIVED"
    after = _ok(client.get(f"{Q}/dashboard"))
    assert after["openClaims"] == 1


def test_dashboard_counts_an_overdue_gauge(qms):
    """교정 기한이 지난 계측기를 센다. 기록이 아예 없는 계측기는 세지 않는다."""
    client, created = qms
    _ok(
        _call(
            client,
            created,
            "POST",
            "/gauges",
            {
                "code": "CAL-NEW",
                "name": "기록 없는 계측기",
                "gaugeKind": "캘리퍼스",
                "calibrationCycleDays": 365,
            },
        ),
        201,
    )
    assert _ok(client.get(f"{Q}/dashboard"))["gaugesDue"] == 0, (
        "교정 기록이 없는 것은 '도래'가 아니다"
    )

    old = _ok(
        _call(
            client,
            created,
            "POST",
            "/gauges",
            {
                "code": "CAL-OLD",
                "name": "지난 계측기",
                "gaugeKind": "캘리퍼스",
                "calibrationCycleDays": 1,
            },
        ),
        201,
    )
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/gauges/{old['id']}/calibrations",
            {"calibratedOn": "2026-01-02", "result": "PASS"},
        ),
        201,
    )
    assert _ok(client.get(f"{Q}/dashboard"))["gaugesDue"] == 1
