"""FS-028b SPC API (AC-170~184). 검증 항목마다 테스트를 나눈다.

SPC 업무 시드는 FS-028c다. 관리 특성·부분군은 테스트가 API로 만든다. FS_TODAY = 2026-09-24.
MES 시드의 진행 중 공정 실행 LT-0023(FG-C200·ASM, 09-23 00:00 시작)을 부분군의 틀로 쓴다.
한계의 적용 시작은 게시 시각(실제 시계)이므로, 게시 뒤 판정 검사는 진행 중 실행에 "지금" 시각으로 기록한다.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from fs.spc import service, stats
from sqlalchemy import text

P = "/api/v1/spc"
SEOUL = ZoneInfo("Asia/Seoul")
RUN_START = datetime(2026, 9, 23, tzinfo=SEOUL)
_keys = count()


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        path if path.startswith("/api") else f"{P}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or f"s{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _module(client, created, key: str, enabled: bool) -> None:
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/api/v1/core/workspace/modules/{key}",
            {"enabled": enabled},
        )
    )


SPC_TABLES = (
    "ocap_check",
    "ocap_item",
    "signal",
    "spec_violation",
    "measurement",
    "control_limit",
    "subgroup",
    "characteristic_rule",
    "characteristic",
)


def _clear_seed(engine, created) -> None:
    with engine.begin() as connection:
        for table in SPC_TABLES:
            connection.execute(
                text(
                    f"DELETE FROM spc.{table} WHERE workspace_id=:w AND generation_id=:g"
                ),
                {"w": created["workspaceId"], "g": created["generationId"]},
            )


def test_seeded_demo(guest_space):
    """FS-028c 시드: 특성 6 · 미조치 2(LT-0017) · 공정능력 충분 4·주의 1·부족 1 · QMS 검사 대기 배지."""
    client, _, _ = guest_space
    board = _ok(client.get(f"{P}/dashboard"))
    assert board["characteristicCount"] == 6 and board["openSignals"] == 2
    assert board["capability"] == {"CAPABLE": 4, "MARGINAL": 1, "INCAPABLE": 1}
    assert board["cards"][0]["code"] == "CH-C200-INJ-H"
    signals = _ok(client.get(f"{P}/signals", params={"status": "open"}))
    assert {(s["lotNo"], s["rule"]) for s in signals} == {
        ("LT-0017", 1),
        ("LT-0017", 3),
    }
    resolved = _ok(client.get(f"{P}/signals", params={"status": "resolved"}))
    assert [(s["characteristicCode"], s["causeCategory"]) for s in resolved] == [
        ("CH-C100-ASM-P", "MACHINE")
    ]
    pending = _ok(
        client.get("/api/v1/qms/lookups/mes-lots", params={"pending": "true"})
    )
    assert {r["lotNo"] for r in pending if r["spcSignal"]} == {"LT-0017"}


@pytest.fixture
def spc(guest_space):
    """시드(FS-028c)를 지운 빈 SPC에 FG-C200 조립 핀 피치(2.49~2.59 mm) 특성 1개."""
    client, created, engine = guest_space
    _clear_seed(engine, created)
    ch = _ok(
        _call(
            client,
            created,
            "POST",
            "/characteristics",
            {
                "code": "CH-C200-ASM-P",
                "itemCode": "FG-C200",
                "processCode": "ASM",
                "name": "핀 피치",
                "unit": "mm",
                "lsl": "2.49",
                "usl": "2.59",
                "target": "2.54",
            },
        ),
        201,
    )
    return client, created, engine, ch


def _record(client, created, ch, at: datetime, values, lot="LT-0023", key=None):
    return _call(
        client,
        created,
        "POST",
        "/subgroups",
        {
            "characteristicId": ch["id"],
            "lotNo": lot,
            "measuredAt": at.isoformat(),
            "values": [str(v) for v in values],
        },
        key,
    )


def _around(center: str, spread: str = "0.004") -> list[Decimal]:
    c, s = Decimal(center), Decimal(spread)
    return [c - s, c, c + s, c - s / 2, c + s / 2]


def _basis(client, created, ch, n=20) -> None:
    """RUN_START+1h부터 1시간 간격으로 중심 2.540 부근 부분군 n개(교대로 위·아래 — 연속 규칙이 생기지 않게)."""
    for i in range(n):
        center = "2.541" if i % 2 else "2.539"
        _ok(
            _record(
                client, created, ch, RUN_START + timedelta(hours=i + 1), _around(center)
            ),
            201,
        )


def _publish(client, created, ch, reason="초기 한계"):
    return _call(
        client,
        created,
        "POST",
        f"/characteristics/{ch['id']}/limits",
        {
            "basisFrom": RUN_START.isoformat(),
            "basisTo": datetime.now(SEOUL).isoformat(),
            "reason": reason,
        },
    )


def _later(client, created, ch, hour: int, values):
    """기준 부분군(1~20시) 뒤 업무 시각 — 한계 적용 시작(마지막 부분군 시각)보다 늦다."""
    return _record(client, created, ch, RUN_START + timedelta(hours=hour), values)


# ---------- 계산 (AC-170·173·174) — DB 없음 ----------


def test_limits_match_formula():
    """AC-170: n=5, A2 0.577·D3 0·D4 2.114."""
    got = stats.limits([Decimal(10), Decimal(12)], [Decimal(1), Decimal(3)])
    assert got == {
        "xbar_cl": Decimal("11.000000"),
        "xbar_ucl": Decimal("12.154000"),
        "xbar_lcl": Decimal("9.846000"),
        "r_cl": Decimal("2.000000"),
        "r_ucl": Decimal("4.228000"),
        "r_lcl": Decimal("0.000000"),
    }


LIMIT = stats.limits(
    [Decimal(10)] * 2, [Decimal(1)] * 2
)  # CL 10, UCL 10.577, LCL 9.423
D5 = Decimal("0.05")


def _rules(previous, point) -> set[int]:
    """모든 규칙을 켜고 판정했을 때 나온 규칙 번호."""
    return {
        rule
        for _, rule, _ in stats.signals(previous, point, Decimal(1), LIMIT, ALL_RULES)
    }


def test_rule_one_on_both_charts():
    assert stats.signals([], Decimal("10.6"), Decimal(1), LIMIT) == [
        ("XBAR", 1, Decimal("10.6"))
    ]
    assert stats.signals([], Decimal(10), Decimal("2.2"), LIMIT) == [
        ("R", 1, Decimal("2.2"))
    ]


def test_rule_two_needs_nine_on_one_side():
    above = [Decimal("10.1")] * 8
    assert ("XBAR", 2, Decimal("10.1")) in stats.signals(
        above, Decimal("10.1"), Decimal(1), LIMIT
    )
    assert stats.signals(above[1:], Decimal("10.1"), Decimal(1), LIMIT) == []
    # 중심선과 같은 값은 연속을 끊는다.
    assert (
        stats.signals([*above[:-1], Decimal(10)], Decimal("10.1"), Decimal(1), LIMIT)
        == []
    )


def test_rule_three_needs_six_monotonic():
    rising = [Decimal(f"9.9{i}") for i in range(5)]  # 9.90 → 9.94
    assert ("XBAR", 3, Decimal("9.95")) in stats.signals(
        rising, Decimal("9.95"), Decimal(1), LIMIT
    )
    assert stats.signals(rising[1:], Decimal("9.95"), Decimal(1), LIMIT) == []
    flat = [*rising[:-1], Decimal("9.93")]  # 같은 값은 끊김
    assert stats.signals(flat, Decimal("9.95"), Decimal(1), LIMIT) == []


ALL_RULES = frozenset(range(1, 9))


def test_rule_four_needs_fourteen_alternating():
    """DSN-17 Q3: Nelson 4. 위아래로 번갈아 14점."""
    alternating = [Decimal(10) + (D5 if i % 2 else -D5) for i in range(13)]
    assert 4 in _rules(alternating, Decimal("10.05"))
    assert 4 not in _rules(alternating[1:], Decimal("10.05"))
    flat = [*alternating[:-1], alternating[-2]]  # 같은 값이 이어지면 번갈기가 끊긴다
    assert 4 not in _rules(flat, Decimal("10.05"))


def test_rules_five_and_six_count_one_side_beyond_zones():
    """Nelson 5(3점 중 2점이 2σ 밖)·6(5점 중 4점이 1σ 밖). 마지막 점 자신이 구역 밖이어야 한다."""
    assert 5 in _rules([Decimal("10.45"), Decimal(10)], Decimal("10.45"))
    assert 5 not in _rules([Decimal(10), Decimal(10)], Decimal("10.45"))
    # 반대쪽 점은 같은 쪽으로 세지 않는다.
    assert 5 not in _rules([Decimal("9.55"), Decimal(10)], Decimal("10.45"))
    beyond = [Decimal("10.25")] * 2 + [Decimal(10), Decimal("10.25")]
    assert 6 in _rules(beyond, Decimal("10.25"))
    assert 6 not in _rules(beyond, Decimal("10.05"))  # 마지막 점이 1σ 안


def test_rules_seven_and_eight_are_about_one_sigma():
    """Nelson 7(1σ 안 15점)·8(1σ 밖 8점, 쪽은 섞여도 된다)."""
    assert 7 in _rules([Decimal("10.05")] * 14, Decimal("10.05"))
    mixed = [Decimal("10.25"), Decimal("9.75")] * 3 + [Decimal("10.25")]
    found = _rules(mixed, Decimal("9.75"))
    assert 8 in found and 2 not in found  # 쪽이 섞였으니 규칙 2는 아니다


def test_only_selected_rules_are_judged():
    nine_above = [Decimal("10.1")] * 8
    assert stats.signals(nine_above, Decimal("10.1"), Decimal(1), LIMIT, {1}) == []
    assert 2 in _rules(nine_above, Decimal("10.1"))


def test_i_mr_uses_moving_range_and_its_own_constants():
    """Q1: n=1은 이웃 차이가 R 자리. 첫 점 MR 0은 평균에서 빠진다(E2 2.660·D4 3.267·d2 1.128)."""
    assert stats.subgroup([Decimal(5)]) == (Decimal("5.000000"), Decimal("0.000000"))
    assert stats.subgroup([Decimal(5)], Decimal(3)) == (
        Decimal("5.000000"),
        Decimal("2.000000"),
    )
    imr = stats.limits([Decimal(10)] * 3, [Decimal(0), Decimal(1), Decimal(1)], 1)
    assert imr["r_cl"] == Decimal("1.000000")  # 0을 세었다면 0.666667
    assert imr["xbar_ucl"] == Decimal("12.660000")
    assert stats.signals([], Decimal(13), Decimal(0), imr, chart_type="I_MR") == [
        ("I", 1, Decimal(13))
    ]


def test_capability_one_sided_and_judgement():
    xbars, ranges = [Decimal(10)] * 20, [Decimal("2.326")] * 20  # σ̂ = 1
    both = stats.capability(xbars, ranges, Decimal(5), Decimal(16))
    assert (both["cp"], both["cpk"], both["judgement"]) == (
        Decimal("1.833333"),
        Decimal("1.666667"),
        "CAPABLE",
    )
    upper = stats.capability(xbars, ranges, None, Decimal(13))
    assert (upper["cp"], upper["cpk"], upper["judgement"]) == (
        None,
        Decimal("1.000000"),
        "MARGINAL",
    )


# ---------- API ----------


def test_guest_has_spc_module(guest_space):
    client, _, _ = guest_space
    modules = {
        m["moduleKey"]: m["enabled"]
        for m in client.get("/api/v1/core/workspace/modules").json()["data"]
    }
    assert modules["spc"] is True


def test_characteristic_rules(spc):
    """MES 완제품만, 중복 409, 부분군이 생기면 규격 변경 409(AC-179)."""
    client, created, _, ch = spc
    body = {
        "code": "CH-X",
        "itemCode": "NO-SUCH",
        "processCode": "ASM",
        "name": "x",
        "unit": "mm",
        "usl": "1",
    }
    bad = _call(client, created, "POST", "/characteristics", body)
    assert (
        bad.status_code == 400
        and "itemCode" in bad.json()["error"]["details"]["fields"]
    )
    dup = _call(
        client,
        created,
        "POST",
        "/characteristics",
        {**body, "itemCode": "FG-C200", "code": ch["code"]},
    )
    assert dup.status_code == 409 and _reason(dup) == "DUPLICATE"
    reversed_spec = _call(
        client,
        created,
        "POST",
        "/characteristics",
        {**body, "itemCode": "FG-C200", "lsl": "2"},
    )
    assert reversed_spec.status_code == 400
    _ok(
        _call(client, created, "PATCH", f"/characteristics/{ch['id']}", {"usl": "2.60"})
    )
    _ok(
        _record(client, created, ch, RUN_START + timedelta(hours=1), _around("2.54")),
        201,
    )
    locked = _call(
        client, created, "PATCH", f"/characteristics/{ch['id']}", {"usl": "2.61"}
    )
    assert locked.status_code == 409 and _reason(locked) == "CHARACTERISTIC_IN_USE"
    renamed = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/characteristics/{ch['id']}",
            {"name": "핀 피치(조립)"},
        )
    )
    assert renamed["name"] == "핀 피치(조립)" and renamed["usl"] == "2.6000"


def test_spec_violation_is_separate_from_control_limit(spc):
    """Q4: 규격 밖 개별값은 한계 게시 전에도 기록되고, 부분군을 무효로 하면 함께 무효가 된다."""
    client, created, _, ch = spc  # 규격 2.49~2.59
    inside = _ok(
        _record(client, created, ch, RUN_START + timedelta(hours=1), _around("2.54")),
        201,
    )
    assert inside["specViolations"] == [] and inside["signals"] == []
    out = _ok(
        _record(
            client,
            created,
            ch,
            RUN_START + timedelta(hours=2),
            [Decimal("2.60"), Decimal("2.48"), *_around("2.54")[:3]],
        ),
        201,
    )
    assert [(v["seq"], v["side"]) for v in out["specViolations"]] == [
        (1, "HIGH"),
        (2, "LOW"),
    ]
    rows = _ok(client.get(f"{P}/spec-violations"))
    assert [(r["seq"], r["side"], r["limitValue"], r["status"]) for r in rows] == [
        (2, "LOW", "2.490000", "open"),
        (1, "HIGH", "2.590000", "open"),
    ]
    assert rows[0]["lotNo"] == "LT-0023" and rows[0]["characteristicCode"] == ch["code"]
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/subgroups/{out['id']}/void",
            {"reason": "오측정"},
        )
    )
    assert _ok(client.get(f"{P}/spec-violations", params={"status": "open"})) == []
    assert len(_ok(client.get(f"{P}/spec-violations", params={"status": "void"}))) == 2
    assert _ok(client.get(f"{P}/dashboard"))["weekSpecViolations"] == 0


def test_characteristic_chart_type_and_rule_selection(spc):
    """Q1·Q3: I-MR은 측정값 1개만 받고, 특성이 고른 규칙만 판정한다."""
    client, created, _, ch = spc
    assert ch["chartType"] == "XBAR_R" and ch["subgroupSize"] == 5 and ch["rules"] == []
    mismatch = _call(
        client,
        created,
        "PATCH",
        f"/characteristics/{ch['id']}",
        {"chartType": "I_MR", "subgroupSize": 5},
    )
    assert (
        mismatch.status_code == 400
        and "subgroupSize" in mismatch.json()["error"]["details"]["fields"]
    )
    # 크기를 따로 주지 않으면 관리도 종류에 맞춰 준다.
    imr = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/characteristics/{ch['id']}",
            {"chartType": "I_MR", "rules": [1, 2, 5]},
        )
    )
    assert imr["subgroupSize"] == 1 and imr["rules"] == [1, 2, 5]
    wrong_count = _record(
        client, created, ch, RUN_START + timedelta(hours=1), _around("2.54")
    )
    assert (
        wrong_count.status_code == 400
        and "values" in wrong_count.json()["error"]["details"]["fields"]
    )
    first = _ok(
        _record(client, created, ch, RUN_START + timedelta(hours=1), [Decimal("2.54")]),
        201,
    )
    assert first["xbar"] == "2.540000" and first["r"] == "0.000000"
    second = _ok(
        _record(client, created, ch, RUN_START + timedelta(hours=2), [Decimal("2.56")]),
        201,
    )
    assert second["r"] == "0.020000"  # 이웃 차이
    no_one = _call(
        client, created, "PATCH", f"/characteristics/{ch['id']}", {"rules": [2, 3]}
    )
    assert (
        no_one.status_code == 400
        and "rules" in no_one.json()["error"]["details"]["fields"]
    )


def test_runs_come_from_mes(spc):
    client, _, _, ch = spc
    items = _ok(client.get(f"{P}/lookups/items"))
    assert {i["itemCode"] for i in items} >= {"FG-C100", "FG-C200", "FG-T300"}
    runs = _ok(client.get(f"{P}/runs", params={"characteristicId": ch["id"]}))
    assert {(r["lotNo"], r["processCode"], r["endedAt"] is None) for r in runs} >= {
        ("LT-0023", "ASM", True)
    }
    assert all(r["itemCode"] == "FG-C200" and r["processCode"] == "ASM" for r in runs)


def test_measured_time_window_order_and_idempotency(spc):
    """AC-175·176."""
    client, created, _, ch = spc
    early = _record(
        client, created, ch, RUN_START - timedelta(hours=1), _around("2.54")
    )
    assert (
        early.status_code == 400
        and "measuredAt" in early.json()["error"]["details"]["fields"]
    )
    wrong_lot = _record(
        client,
        created,
        ch,
        RUN_START + timedelta(hours=1),
        _around("2.54"),
        lot="LT-0001",
    )
    assert (
        wrong_lot.status_code == 400
        and "lotNo" in wrong_lot.json()["error"]["details"]["fields"]
    )
    first = _ok(
        _record(
            client,
            created,
            ch,
            RUN_START + timedelta(hours=5),
            _around("2.54"),
            key="same",
        ),
        201,
    )
    again = _ok(
        _record(
            client,
            created,
            ch,
            RUN_START + timedelta(hours=5),
            _around("2.54"),
            key="same",
        ),
        201,
    )
    assert first["id"] == again["id"]
    assert (first["xbar"], first["r"], first["equipmentCode"]) == (
        "2.540000",
        "0.008000",
        "ASM-03",
    )
    older = _record(
        client, created, ch, RUN_START + timedelta(hours=4), _around("2.54")
    )
    assert (
        older.status_code == 400
        and "마지막 부분군" in older.json()["error"]["details"]["fields"]["measuredAt"]
    )
    assert (
        len(_ok(client.get(f"{P}/subgroups", params={"characteristicId": ch["id"]})))
        == 1
    )


def test_limit_needs_twenty_and_judges_after_publish(spc):
    """AC-171·172·173: 20개 미만 400, 게시 전 부분군은 판정 안 함, 게시 뒤 한계 밖은 규칙 1."""
    client, created, _, ch = spc
    _ok(
        _record(
            client, created, ch, RUN_START + timedelta(minutes=30), _around("2.60")
        ),
        201,
    )  # 게시 전 — 판정 없음
    _basis(client, created, ch, 18)
    short = _publish(client, created, ch)
    assert short.status_code == 400
    _ok(
        _record(client, created, ch, RUN_START + timedelta(hours=30), _around("2.540")),
        201,
    )
    preview = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/limits/preview",
            params={
                "basisFrom": RUN_START.isoformat(),
                "basisTo": datetime.now(SEOUL).isoformat(),
            },
        )
    )
    limit = _ok(_publish(client, created, ch), 201)
    assert (limit["version"], limit["basisCount"], limit["xbarUcl"]) == (
        1,
        20,
        preview["xbarUcl"],
    )
    assert _ok(client.get(f"{P}/signals")) == []
    out = _ok(_later(client, created, ch, 31, _around("2.700")), 201)
    assert {(s["chart"], s["rule"]) for s in out["signals"]} == {("XBAR", 1)}
    signal = _ok(client.get(f"{P}/signals", params={"status": "open"}))[0]
    assert (signal["lotNo"], signal["limitVersion"], signal["equipmentCode"]) == (
        "LT-0023",
        1,
        "ASM-03",
    )
    chart = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/chart", params={"from": "2026-09-01"}
        )
    )
    versions = [p["limitVersion"] for p in chart["points"]]
    assert versions[:-1] == [None] * 20 and versions[-1] == 1


def test_trend_counts_restart_with_new_version(spc):
    """AC-174: 같은 버전에서 5점 상승 뒤 새 버전을 게시하면 6번째 상승점에 규칙 3이 없다."""
    client, created, _, ch = spc
    _basis(client, created, ch, 20)
    _ok(_publish(client, created, ch), 201)
    again = _publish(client, created, ch, "재게시")
    assert again.status_code == 409 and _reason(again) == "NO_NEW_SUBGROUP"
    for hour, center in zip(
        range(21, 26), ("2.5400", "2.5405", "2.5410", "2.5415", "2.5420"), strict=True
    ):
        assert (
            _ok(_later(client, created, ch, hour, _around(center)), 201)["signals"]
            == []
        )
    _ok(_publish(client, created, ch, "재산정"), 201)
    sixth = _ok(_later(client, created, ch, 26, _around("2.5425")), 201)
    assert sixth["signals"] == []


def test_resolve_and_void(spc):
    """AC-177·178."""
    client, created, _, ch = spc
    _basis(client, created, ch, 20)
    _ok(_publish(client, created, ch), 201)
    bad = _ok(_later(client, created, ch, 21, _around("2.700")), 201)
    signal_id = _ok(client.get(f"{P}/signals"))[0]["id"]
    missing = _call(
        client,
        created,
        "POST",
        f"/signals/{signal_id}/resolve",
        {"causeCategory": "MACHINE"},
    )
    assert missing.status_code == 400
    done = _ok(
        _call(
            client,
            created,
            "POST",
            f"/signals/{signal_id}/resolve",
            {"causeCategory": "MACHINE", "action": "지그 교체"},
        )
    )
    assert (done["status"], done["causeCategory"]) == ("resolved", "MACHINE")
    again = _call(
        client,
        created,
        "POST",
        f"/signals/{signal_id}/resolve",
        {"causeCategory": "MAN", "action": "재교육"},
    )
    assert again.status_code == 409 and _reason(again) == "NOT_OPEN"
    before = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/capability", params={"from": "2026-09-01"}
        )
    )
    voided = _ok(
        _call(
            client,
            created,
            "POST",
            f"/subgroups/{bad['id']}/void",
            {"reason": "측정기 영점 오류"},
        )
    )
    assert (voided["status"], voided["voidedSignals"]) == ("void", 1)
    assert _ok(client.get(f"{P}/signals"))[0]["status"] == "void"
    after = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/capability", params={"from": "2026-09-01"}
        )
    )
    assert (before["subgroupCount"], after["subgroupCount"]) == (21, 20)
    assert Decimal(after["mu"]) < Decimal(before["mu"])


def test_capability_needs_twenty(spc):
    """AC-180."""
    client, created, _, ch = spc
    _basis(client, created, ch, 19)
    thin = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/capability", params={"from": "2026-09-01"}
        )
    )
    assert thin["insufficient"] is True and "cpk" not in thin
    _ok(
        _record(client, created, ch, RUN_START + timedelta(hours=40), _around("2.540")),
        201,
    )
    full = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/capability", params={"from": "2026-09-01"}
        )
    )
    assert (
        full["insufficient"] is False
        and full["judgement"] == "CAPABLE"
        and len(full["histogram"]) == 10
    )


def test_mes_off_blocks_only_measuring(spc):
    """AC-181."""
    client, created, _, ch = spc
    _basis(client, created, ch, 20)
    _module(client, created, "mes", False)
    runs = client.get(f"{P}/runs", params={"characteristicId": ch["id"]})
    assert runs.status_code == 409 and _reason(runs) == "SOURCE_MODULE_DISABLED"
    assert _reason(client.get(f"{P}/lookups/items")) == "SOURCE_MODULE_DISABLED"
    blocked = _record(
        client, created, ch, RUN_START + timedelta(hours=30), _around("2.54")
    )
    assert blocked.status_code == 409 and _reason(blocked) == "SOURCE_MODULE_DISABLED"
    _ok(_publish(client, created, ch), 201)
    assert (
        len(
            _ok(
                client.get(
                    f"{P}/characteristics/{ch['id']}/chart",
                    params={"from": "2026-09-01"},
                )
            )["points"]
        )
        == 20
    )
    assert _ok(client.get(f"{P}/dashboard"))["characteristicCount"] == 1


def test_qms_badge_follows_open_signals(spc):
    """AC-182: 미조치 이상 LOT만 true, SPC를 끄면 null이고 QMS는 그대로."""
    client, created, engine, ch = spc
    _basis(client, created, ch, 20)
    _ok(_publish(client, created, ch), 201)
    _ok(_later(client, created, ch, 21, _around("2.700")), 201)
    # LT-0023은 진행 중이라 QMS 검사 대기에 없다 — 이상 LOT 번호를 검사 대기 LOT으로 바꿔 배지 경로를 본다.
    pending = _ok(
        client.get("/api/v1/qms/lookups/mes-lots", params={"pending": "true"})
    )
    target = pending[0]["lotNo"]
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE spc.signal SET lot_no=:lot WHERE workspace_id=:w AND generation_id=:g"
            ),
            {"lot": target, "w": created["workspaceId"], "g": created["generationId"]},
        )
    badges = {
        r["lotNo"]: r["spcSignal"]
        for r in _ok(
            client.get("/api/v1/qms/lookups/mes-lots", params={"pending": "true"})
        )
    }
    assert badges[target] is True and not any(
        v for k, v in badges.items() if k != target
    )
    _module(client, created, "spc", False)
    off = _ok(client.get("/api/v1/qms/lookups/mes-lots", params={"pending": "true"}))
    assert all(r["spcSignal"] is None for r in off)
    assert all(
        r["spcSignal"] is None for r in _ok(client.get("/api/v1/qms/inspections"))
    )
    assert client.get(f"{P}/dashboard").status_code == 409


def test_chart_without_end_date_includes_measurements_after_business_day(
    spc, monkeypatch
):
    """종료일이 없으면 업무 기준일(FS_TODAY 09-24)보다 늦게 측정한 부분군도 관리도에 보인다."""
    client, created, _, ch = spc
    # The open-ended run uses the DB clock, which can differ from the host.
    # Fix this test's clock and measurement after FS_TODAY instead of depending
    # on wall-clock time or allowing out-of-period measurements in the product.
    late = datetime(2026, 9, 25, 10, tzinfo=SEOUL)
    monkeypatch.setattr(service, "_now", lambda _: late + timedelta(minutes=1))
    _basis(client, created, ch, 20)
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/characteristics/{ch['id']}/limits",
            {
                "basisFrom": RUN_START.isoformat(),
                "basisTo": "2026-09-24T00:00:00+09:00",
                "reason": "초기 한계",
            },
        ),
        201,
    )
    _ok(_record(client, created, ch, late, _around("2.700")), 201)
    points = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/chart", params={"from": "2026-09-01"}
        )
    )["points"]
    assert points[-1]["signals"] and points[-1]["limitVersion"] == 1
    bounded = _ok(
        client.get(
            f"{P}/characteristics/{ch['id']}/chart",
            params={"from": "2026-09-01", "to": "2026-09-24"},
        )
    )["points"]
    assert len(bounded) == 20


def test_other_workspace_cannot_see_spc(spc):
    """AC-183"""
    client, _, _, ch = spc
    other = TestClient(client.app, base_url="https://testserver")
    assert (
        other.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "테스트 게스트"},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 201
    )
    assert other.get(f"{P}/characteristics/{ch['id']}").status_code == 404
    assert ch["id"] not in {
        c["id"] for c in other.get(f"{P}/characteristics").json()["data"]
    }


def _ocap(client, created, body, key=None):
    return _call(client, created, "POST", "/ocap-items", body, key)


def test_ocap_items_scope_and_duplicate(spc):
    """Q5: 특성·규칙이 비면 '모든 것'. DB UK가 NULL을 못 잡으므로 서비스가 같은 순서를 막는다."""
    client, created, _, ch = spc
    # 화면은 '모든 것'을 null로 보낸다. 키를 빼고 보내는 것과 같아야 한다.
    common = _ok(
        _ocap(
            client,
            created,
            {
                "seq": 1,
                "checkText": "설비 공기압 확인",
                "characteristicId": None,
                "ruleNo": None,
                "causeCategory": None,
            },
        ),
        201,
    )
    assert common["characteristicId"] is None and common["ruleNo"] is None
    same = _ocap(client, created, {"seq": 1, "checkText": "다른 내용"})
    assert same.status_code == 409 and _reason(same) == "DUPLICATE"
    # 적용 범위가 다르면 같은 순서를 쓸 수 있다.
    scoped = _ok(
        _ocap(
            client,
            created,
            {
                "seq": 1,
                "checkText": "금형 핀 마모 확인",
                "characteristicId": ch["id"],
                "ruleNo": 1,
                "causeCategory": "MACHINE",
            },
        ),
        201,
    )
    assert scoped["causeCategory"] == "MACHINE"
    assert [i["id"] for i in _ok(client.get(f"{P}/ocap-items"))] == [
        common["id"],
        scoped["id"],
    ]


def test_ocap_must_be_recorded_before_resolving(spc):
    """Q5: 해당 점검 항목을 모두 기록해야 조치를 닫을 수 있다. NG는 메모가 필요하다."""
    client, created, _, ch = spc
    common = _ok(
        _ocap(client, created, {"seq": 1, "checkText": "설비 공기압 확인"}), 201
    )
    rule_one = _ok(
        _ocap(
            client,
            created,
            {
                "seq": 1,
                "checkText": "측정기 영점 확인",
                "ruleNo": 1,
                "causeCategory": "MEASUREMENT",
            },
        ),
        201,
    )
    other_rule = _ok(
        _ocap(client, created, {"seq": 2, "checkText": "규칙 2 전용", "ruleNo": 2}), 201
    )
    _basis(client, created, ch)
    _ok(_publish(client, created, ch), 201)
    out = _ok(_later(client, created, ch, 21, _around("2.700")), 201)
    signal = _ok(client.get(f"{P}/signals", params={"status": "open"}))[0]
    assert signal["rule"] == 1 and out["signals"]

    checklist = _ok(client.get(f"{P}/signals/{signal['id']}/ocap"))
    assert [i["id"] for i in checklist["items"]] == [common["id"], rule_one["id"]]
    assert other_rule["id"] not in [i["id"] for i in checklist["items"]]
    assert checklist["missing"] == [common["id"], rule_one["id"]]

    blocked = _call(
        client,
        created,
        "POST",
        f"/signals/{signal['id']}/resolve",
        {"causeCategory": "MACHINE", "action": "지그 재조정"},
    )
    assert blocked.status_code == 409 and _reason(blocked) == "OCAP_INCOMPLETE"

    no_note = _call(
        client,
        created,
        "POST",
        f"/signals/{signal['id']}/ocap",
        {"checks": [{"ocapItemId": common["id"], "result": "NG"}]},
    )
    assert no_note.status_code == 400

    recorded = _ok(
        _call(
            client,
            created,
            "POST",
            f"/signals/{signal['id']}/ocap",
            {
                "checks": [
                    {"ocapItemId": common["id"], "result": "OK"},
                    {
                        "ocapItemId": rule_one["id"],
                        "result": "NG",
                        "note": "영점이 0.01 밀려 있었다",
                    },
                ]
            },
        )
    )
    assert recorded["missing"] == []
    assert [i["check"]["result"] for i in recorded["items"]] == ["OK", "NG"]

    resolved = _ok(
        _call(
            client,
            created,
            "POST",
            f"/signals/{signal['id']}/resolve",
            {"causeCategory": "MEASUREMENT", "action": "영점 재조정"},
        )
    )
    assert resolved["status"] == "resolved"
    late = _call(
        client,
        created,
        "POST",
        f"/signals/{signal['id']}/ocap",
        {"checks": [{"ocapItemId": common["id"], "result": "NA"}]},
    )
    assert late.status_code == 409 and _reason(late) == "NOT_OPEN"


def test_ocap_item_scope_is_locked_once_checked(spc):
    """기록이 생긴 항목의 적용 범위는 바꿀 수 없다. 내용·순서·사용 여부는 바꿀 수 있다."""
    client, created, _, ch = spc
    item = _ok(_ocap(client, created, {"seq": 1, "checkText": "설비 공기압 확인"}), 201)
    _basis(client, created, ch)
    _ok(_publish(client, created, ch), 201)
    _ok(_later(client, created, ch, 21, _around("2.700")), 201)
    signal = _ok(client.get(f"{P}/signals", params={"status": "open"}))[0]
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/signals/{signal['id']}/ocap",
            {"checks": [{"ocapItemId": item["id"], "result": "OK"}]},
        )
    )
    locked = _call(
        client,
        created,
        "PATCH",
        f"/ocap-items/{item['id']}",
        {"ruleNo": 2},
    )
    assert locked.status_code == 409 and _reason(locked) == "OCAP_ITEM_IN_USE"
    edited = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/ocap-items/{item['id']}",
            {"checkText": "설비 공기압 6bar 확인", "isActive": False},
        )
    )
    assert (
        edited["checkText"] == "설비 공기압 6bar 확인" and edited["isActive"] is False
    )
    # 사용을 꺼도 이미 기록한 항목은 그 이상의 점검표에 남는다.
    checklist = _ok(client.get(f"{P}/signals/{signal['id']}/ocap"))
    assert [i["id"] for i in checklist["items"]] == [item["id"]]
    assert checklist["missing"] == []
