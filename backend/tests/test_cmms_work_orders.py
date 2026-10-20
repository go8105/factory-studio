"""CMMS-1d: 작업지시(C-03)·전환 대기 신호(C-02)·정비원과 외주 업체(C-08).

FS-029 D47·D48 — 접수 → 진행 → 완료/취소, 완료·취소 뒤 불변.
신호 1건당 취소되지 않은 작업지시 1건이고, 전환해도 원천 상태는 바뀌지 않는다.
"""

from itertools import count

import pytest
from sqlalchemy import text

C = "/api/v1/cmms"
_keys = count()


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        path if path.startswith("/api") else f"{C}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or f"d{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


@pytest.fixture
def cmms(guest_space):
    """설비 하나와 정비원 하나가 있는 빈 CMMS."""
    client, created, engine = guest_space
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM cmms.asset WHERE workspace_id=:w AND generation_id=:g"),
            {"w": created["workspaceId"], "g": created["generationId"]},
        )
    asset = _ok(
        _call(
            client,
            created,
            "POST",
            "/assets",
            {"code": "PRESS-01", "name": "프레스 1호", "assetType": "OTHER"},
        ),
        201,
    )
    technician = _ok(
        _call(
            client,
            created,
            "POST",
            "/technicians",
            {
                "code": "T-01",
                "name": "김보전",
                "skill": "MECHANICAL",
                "hourlyRate": "30000",
            },
        ),
        201,
    )
    return client, created, engine, asset, technician


def _order(client, created, asset, **extra):
    return _call(
        client,
        created,
        "POST",
        "/work-orders",
        {"assetId": asset["id"], "title": "이상 소음", **extra},
    )


# ---------- 작업지시 상태 전이 (C-03, D47) ----------


def test_work_order_runs_through_the_whole_flow(cmms):
    """접수 → 진행 → 작업 기록 → 완료. 고장이면 복구 시각이 자동으로 찍힌다."""
    client, created, _, asset, tech = cmms
    order = _ok(_order(client, created, asset, technicianId=tech["id"]), 201)
    assert order["woNo"] == "WO-0001"
    assert order["status"] == "REQUESTED" and order["kind"] == "BM"
    assert order["source"] == "MANUAL" and order["sourceRef"] is None
    assert order["failureAt"] and order["startedAt"] is None
    assert order["technicianName"] == "김보전"

    # 진행 전에는 작업 기록을 남길 수 없다.
    early = _call(
        client, created, "POST", f"/work-orders/{order['id']}/logs", {"minutes": 30}
    )
    assert early.status_code == 409 and _reason(early) == "NOT_IN_PROGRESS"

    started = _ok(
        _call(client, created, "POST", f"/work-orders/{order['id']}/start", {})
    )
    assert started["status"] == "IN_PROGRESS" and started["startedAt"]

    logged = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/logs",
            {"minutes": 40, "note": "호스 교체"},
            key="log-1",
        ),
        201,
    )
    assert [(x["minutes"], x["technicianName"]) for x in logged["logs"]] == [
        (40, "김보전")
    ]

    completed = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/complete",
            {"causeCategory": "WEAR", "action": "냉각수 호스 교체"},
        )
    )
    assert completed["status"] == "COMPLETED"
    assert completed["causeCategory"] == "WEAR" and completed["restoredAt"]
    assert completed["completedAt"]

    # 완료 뒤에는 어떤 전이도 되지 않는다 — 지표가 이 시각들로 계산되기 때문이다.
    for path, body in (
        ("start", {}),
        ("complete", {"causeCategory": "OTHER", "action": "다시"}),
        ("cancel", {"reason": "되돌리기"}),
    ):
        again = _call(
            client, created, "POST", f"/work-orders/{order['id']}/{path}", body
        )
        assert again.status_code == 409, path


def test_work_order_can_be_cancelled_before_completion(cmms):
    client, created, _, asset, _tech = cmms
    order = _ok(_order(client, created, asset), 201)
    cancelled = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/cancel",
            {"reason": "오인 신고"},
        )
    )
    assert (
        cancelled["status"] == "CANCELLED" and cancelled["cancelReason"] == "오인 신고"
    )
    assert (
        _call(
            client, created, "POST", f"/work-orders/{order['id']}/start", {}
        ).status_code
        == 409
    )


def test_completion_needs_cause_and_action(cmms):
    """원인·조치가 없으면 닫을 수 없다. 외주 비용만 적고 업체를 비우는 것도 막는다."""
    client, created, _, asset, _tech = cmms
    order = _ok(_order(client, created, asset), 201)
    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))

    missing = _call(client, created, "POST", f"/work-orders/{order['id']}/complete", {})
    assert missing.status_code == 400

    short = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/complete",
        {"causeCategory": "WEAR", "action": "x"},
    )
    assert short.status_code == 400

    no_vendor = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/complete",
        {"causeCategory": "WEAR", "action": "교체", "externalCost": "100000"},
    )
    assert no_vendor.status_code == 400
    assert "vendorId" in no_vendor.json()["error"]["details"]["fields"]


def test_failure_codes_must_match_their_kind(cmms):
    """증상 칸에 조치 코드를 넣는 실수를 막는다."""
    client, created, _, asset, _tech = cmms
    action_code = _ok(
        _call(
            client,
            created,
            "POST",
            "/failure-codes",
            {"kind": "ACTION", "code": "REPLACE", "name": "교체"},
        ),
        201,
    )
    wrong = _order(client, created, asset, symptomCodeId=action_code["id"])
    assert wrong.status_code == 400
    assert "symptomCodeId" in wrong.json()["error"]["details"]["fields"]

    symptom = _ok(
        _call(
            client,
            created,
            "POST",
            "/failure-codes",
            {"kind": "SYMPTOM", "code": "NOISE", "name": "이상 소음"},
        ),
        201,
    )
    order = _ok(_order(client, created, asset, symptomCodeId=symptom["id"]), 201)
    assert order["symptomCode"] == "NOISE"
    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    bad_action = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/complete",
        {
            "causeCategory": "WEAR",
            "action": "교체함",
            "actionCodeId": symptom["id"],
        },
    )
    assert bad_action.status_code == 400


def test_inactive_asset_cannot_take_new_orders(cmms):
    client, created, _, asset, _tech = cmms
    _ok(_call(client, created, "PATCH", f"/assets/{asset['id']}", {"isActive": False}))
    blocked = _order(client, created, asset)
    assert blocked.status_code == 409 and _reason(blocked) == "ASSET_INACTIVE"


# ---------- 전환 대기 신호 (C-02, D48) ----------


def test_pending_signals_come_from_bems_and_spc(cmms):
    """원천을 끄면 그 줄만 비고 전체가 막히지는 않는다."""
    client, created, _, _asset, _tech = cmms
    data = _ok(client.get(f"{C}/signals"))
    assert data["sources"] == {"bems": True, "spc": True}
    assert isinstance(data["signals"], list)
    for row in data["signals"]:
        assert row["source"] in ("BEMS_ALARM", "SPC_SIGNAL")
        assert row["sourceRef"] and row["summary"]

    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/bems",
            {"enabled": False},
        )
    )
    after = _ok(client.get(f"{C}/signals"))
    assert after["sources"]["bems"] is False and after["sources"]["spc"] is True
    assert all(s["source"] != "BEMS_ALARM" for s in after["signals"])


def test_converting_a_signal_is_once_until_cancelled(cmms):
    """신호 1건당 취소되지 않은 작업지시 1건. 취소하면 다시 전환할 수 있다(UK_PARTIAL)."""
    client, created, _, asset, _tech = cmms
    data = _ok(client.get(f"{C}/signals"))
    if not data["signals"]:
        pytest.skip("시드에 전환할 신호가 없다")
    signal = data["signals"][0]
    payload = {
        "source": signal["source"],
        "sourceRef": signal["sourceRef"],
        "summary": signal["summary"],
        "assetId": asset["id"],
    }
    order = _ok(_call(client, created, "POST", "/signals/convert", payload), 201)
    assert order["source"] == signal["source"]
    assert order["sourceRef"] == signal["sourceRef"]
    assert order["sourceSummary"] == signal["summary"]

    # 전환한 신호는 대기 목록에서 빠진다.
    rest = _ok(client.get(f"{C}/signals"))
    assert all(s["id"] != signal["id"] for s in rest["signals"])

    duplicate = _call(
        client, created, "POST", "/signals/convert", payload, key="convert-again"
    )
    assert duplicate.status_code == 409 and _reason(duplicate) == "ALREADY_CONVERTED"

    _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/cancel",
            {"reason": "설비가 아니라 자재 문제였다"},
        )
    )
    back = _ok(client.get(f"{C}/signals"))
    assert any(s["id"] == signal["id"] for s in back["signals"])
    assert (
        _call(
            client, created, "POST", "/signals/convert", payload, key="convert-3"
        ).status_code
        == 201
    )


def test_conversion_does_not_touch_the_source(cmms):
    """전환해도 BEMS 경보·SPC 이상의 상태는 그대로다(D48)."""
    client, created, engine, asset, _tech = cmms
    data = _ok(client.get(f"{C}/signals"))
    signal = next((s for s in data["signals"] if s["source"] == "BEMS_ALARM"), None)
    if signal is None:
        pytest.skip("시드에 BEMS 경보가 없다")
    counts = (
        "SELECT (SELECT count(*) FROM bems.alarm WHERE workspace_id=:w AND status<>'cleared'), "
        "(SELECT count(*) FROM spc.signal WHERE workspace_id=:w AND status='open')"
    )
    with engine.connect() as c:
        before = c.execute(text(counts), {"w": created["workspaceId"]}).one()
    _ok(
        _call(
            client,
            created,
            "POST",
            "/signals/convert",
            {
                "source": signal["source"],
                "sourceRef": signal["sourceRef"],
                "summary": signal["summary"],
                "assetId": asset["id"],
            },
        ),
        201,
    )
    with engine.connect() as c:
        after = c.execute(text(counts), {"w": created["workspaceId"]}).one()
    assert before == after


# ---------- 정비원·외주 업체 (C-08, Q5) ----------


def test_technician_and_vendor_masters(cmms):
    client, created, _, asset, tech = cmms
    assert tech["hourlyRate"] == "30000.00" and tech["currency"] == "KRW"

    vendor = _ok(
        _call(
            client,
            created,
            "POST",
            "/vendors",
            {"code": "V-01", "name": "한빛정비", "phone": "02-000-0000"},
        ),
        201,
    )
    assert vendor["isActive"] is True

    # 작업지시가 쓰고 있으면 정비원을 지울 수 없다.
    order = _ok(_order(client, created, asset, technicianId=tech["id"]), 201)
    blocked = _call(client, created, "DELETE", f"/technicians/{tech['id']}")
    assert blocked.status_code == 409 and _reason(blocked) == "REFERENCED_BY_OTHERS"

    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    done = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/complete",
            {
                "causeCategory": "EXTERNAL",
                "action": "외주 수리",
                "vendorId": vendor["id"],
                "externalCost": "250000",
            },
        )
    )
    assert done["vendorName"] == "한빛정비" and done["externalCost"] == "250000.00"

    # 쓰지 않는 업체는 지울 수 있다.
    spare = _ok(
        _call(client, created, "POST", "/vendors", {"code": "V-02", "name": "미사용"}),
        201,
    )
    assert (
        _call(client, created, "DELETE", f"/vendors/{spare['id']}").status_code == 204
    )


def test_lookups_degrade_when_the_source_is_off(cmms):
    """HR·ERP를 꺼도 목록이 비기만 한다 — 코드를 손으로 적으면 된다."""
    client, created, _, _asset, _tech = cmms
    assert isinstance(_ok(client.get(f"{C}/lookups/hr-employees")), list)
    assert isinstance(_ok(client.get(f"{C}/lookups/erp-partners")), list)
    for module in ("hr", "erp"):
        _ok(
            _call(
                client,
                created,
                "PATCH",
                f"/api/v1/core/workspace/modules/{module}",
                {"enabled": False},
            )
        )
    assert _ok(client.get(f"{C}/lookups/hr-employees")) == []
    assert _ok(client.get(f"{C}/lookups/erp-partners")) == []
