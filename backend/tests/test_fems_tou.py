"""FEMS-1c: TOU 시간대별 요금(F05·F41)과 부하 패턴·피크(F25·F26) — DSN-15 Q1·Q2.

구간표는 **계절·요일마다 0~24시를 빈틈·겹침 없이** 덮어야 한다. DB CHECK는 구간 하나의 모양까지만
보므로 서비스가 집합으로 본다. 수요전력은 **1시간 계측의 최대값 근사**다(Q2) — 15분 계측은 없다.
"""

from datetime import date
from decimal import Decimal
from itertools import count

import pytest
from fs.fems import tou

F = "/api/v1/fems"
_keys = count()


@pytest.fixture
def fems(guest_space):
    return guest_space


def _headers(created):
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": f"tou{next(_keys)}",
    }


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _elec_source(client) -> int:
    rows = client.get(f"{F}/energy-sources").json()["data"]
    return next(r["id"] for r in rows if r["sourceCode"] == "ELEC")


def _full_bands(rate="100") -> list[dict]:
    """3계절 × 3요일을 하루 한 구간으로 덮는 최소 구간표."""
    return [
        {
            "season": season,
            "dayKind": day_kind,
            "hourFrom": 0,
            "hourTo": 24,
            "loadBand": "MID",
            "rate": rate,
        }
        for season in tou.SEASONS
        for day_kind in tou.DAY_KINDS
    ]


def _tou_tariff(client, created, **extra) -> dict:
    """시드 ELEC 요금제(2025-09~)와 겹치지 않도록 기본은 2020년에 둔다."""
    body = {
        "energySourceId": _elec_source(client),
        "tariffCode": "TR-TOU-01",
        "name": "산업용(을) 고압A · 시간대별",
        "basicCharge": "8320",
        "usageRate": "0",
        "effectiveFrom": "2020-01",
        "effectiveTo": "2020-12",
        "tariffKind": "TOU",
        "contractKw": "300",
        **extra,
    }
    return _ok(client.post(f"{F}/tariffs", json=body, headers=_headers(created)), 201)


def _make_current_tariff_tou(client, created, month: str) -> dict:
    """그 달에 적용 중인 ELEC 요금제를 TOU로 바꾼다.

    새 요금제를 끼워 넣으면 기간이 겹친다. 바꾸는 쪽이 적용 기간을 건드리지 않아 깔끔하다.
    """
    source_id = _elec_source(client)
    rows = client.get(f"{F}/tariffs").json()["data"]
    current = next(
        r
        for r in rows
        if r["energySourceId"] == source_id
        and r["effectiveFrom"] <= month
        and (r["effectiveTo"] is None or r["effectiveTo"] >= month)
    )
    return _ok(
        client.patch(
            f"{F}/tariffs/{current['id']}",
            json={"tariffKind": "TOU", "contractKw": "300", "basicCharge": "8320"},
            headers=_headers(created),
        )
    )


# ---------- 코드 상수 (DB가 아니다) ----------


def test_seasons_follow_the_korean_industrial_calendar():
    assert tou.season_of(7) == tou.SUMMER
    assert tou.season_of(12) == tou.WINTER and tou.season_of(1) == tou.WINTER
    assert tou.season_of(4) == tou.SPRING_FALL and tou.season_of(10) == tou.SPRING_FALL


def test_holiday_beats_saturday():
    """휴일에 토요일 요율을 쓰면 안 된다. 일요일은 달력에 없어도 휴일이다."""
    saturday, sunday = date(2026, 10, 31), date(2026, 11, 1)
    assert tou.day_kind_of(saturday, set()) == tou.SATURDAY
    assert tou.day_kind_of(saturday, {saturday}) == tou.HOLIDAY
    assert tou.day_kind_of(sunday, set()) == tou.HOLIDAY
    assert tou.day_kind_of(date(2026, 10, 30), set()) == tou.WEEKDAY


def test_coverage_finds_gaps_overlaps_and_missing_combinations():
    assert tou.coverage_errors(_full_bands_raw()) == []

    gap = [b for b in _full_bands_raw() if b["season"] != tou.SUMMER]
    assert any("여름" in e for e in tou.coverage_errors(gap))

    partial = [b for b in _full_bands_raw() if b["day_kind"] != tou.WEEKDAY]
    partial += [
        {"season": s, "day_kind": tou.WEEKDAY, "hour_from": 0, "hour_to": 9}
        for s in tou.SEASONS
    ]
    partial += [
        {"season": s, "day_kind": tou.WEEKDAY, "hour_from": 12, "hour_to": 24}
        for s in tou.SEASONS
    ]
    errors = tou.coverage_errors(partial)
    assert len(errors) == 3 and all("9~12시가 비어 있습니다" in e for e in errors)

    overlap = [b for b in _full_bands_raw() if b["day_kind"] != tou.SATURDAY]
    overlap += [
        {"season": s, "day_kind": tou.SATURDAY, "hour_from": 0, "hour_to": 20}
        for s in tou.SEASONS
    ]
    overlap += [
        {"season": s, "day_kind": tou.SATURDAY, "hour_from": 18, "hour_to": 24}
        for s in tou.SEASONS
    ]
    assert all("18~20시가 겹칩니다" in e for e in tou.coverage_errors(overlap))


def _full_bands_raw() -> list[dict]:
    return [
        {"season": s, "day_kind": d, "hour_from": 0, "hour_to": 24}
        for s in tou.SEASONS
        for d in tou.DAY_KINDS
    ]


# ---------- 구간표 저장 ----------


def test_bands_are_rejected_when_the_day_is_not_covered(fems):
    client, created, _ = fems
    tariff = _tou_tariff(client, created)
    half = [b for b in _full_bands() if b["season"] != "SUMMER"]
    response = client.put(
        f"{F}/tariffs/{tariff['id']}/bands",
        json={"bands": half},
        headers=_headers(created),
    )
    assert response.status_code == 400
    assert "여름" in response.json()["error"]["details"]["fields"]["bands"]


def test_flat_tariff_takes_no_bands(fems):
    """단일요금제에 구간을 두면 요금이 두 갈래로 계산된다. 막는다."""
    client, created, _ = fems
    flat = _ok(
        client.post(
            f"{F}/tariffs",
            json={
                "energySourceId": _elec_source(client),
                "tariffCode": "TR-FLAT-9",
                "name": "단일",
                "basicCharge": "1000",
                "usageRate": "100",
                "effectiveFrom": "2019-01",
                "effectiveTo": "2019-12",
            },
            headers=_headers(created),
        ),
        201,
    )
    response = client.put(
        f"{F}/tariffs/{flat['id']}/bands",
        json={"bands": _full_bands()},
        headers=_headers(created),
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "NOT_TOU"


def test_bands_replace_wholesale_and_show_up_on_the_tariff(fems):
    client, created, _ = fems
    tariff = _tou_tariff(client, created)
    saved = _ok(
        client.put(
            f"{F}/tariffs/{tariff['id']}/bands",
            json={"bands": _full_bands()},
            headers=_headers(created),
        )
    )
    assert len(saved["bands"]) == 9

    # 다시 넣으면 통째로 바뀐다 — 쌓이지 않는다.
    again = _ok(
        client.put(
            f"{F}/tariffs/{tariff['id']}/bands",
            json={"bands": _full_bands(rate="200")},
            headers=_headers(created),
        )
    )
    assert len(again["bands"]) == 9
    assert {b["rate"] for b in again["bands"]} == {"200.0000"}

    detail = _ok(client.get(f"{F}/tariffs/{tariff['id']}"))
    assert detail["tariffKind"] == "TOU" and detail["contractKw"] == "300.00"
    assert len(detail["bands"]) == 9


def test_flat_tariff_detail_has_no_bands(fems):
    client, _, _ = fems
    rows = client.get(f"{F}/tariffs").json()["data"]
    detail = _ok(client.get(f"{F}/tariffs/{rows[0]['id']}"))
    assert detail["tariffKind"] == "FLAT" and detail["bands"] == []


# ---------- 요금 산정 ----------


def test_tou_billing_uses_contract_power_and_hourly_rates(fems):
    """TOU 요금 = 계약전력 × 기본요금 단가 + Σ(시간 사용량 × 그 시각 요율)."""
    client, created, _ = fems
    billing = _ok(client.get(f"{F}/billing"))
    month = billing["period"]["to"]
    source_id = _elec_source(client)

    tariff = _make_current_tariff_tou(client, created, month)
    _ok(
        client.put(
            f"{F}/tariffs/{tariff['id']}/bands",
            json={"bands": _full_bands(rate="100")},
            headers=_headers(created),
        )
    )
    after = _ok(client.get(f"{F}/billing?from={month}&to={month}"))
    elec = next(s for s in after["sources"] if s["energySourceId"] == source_id)
    segment = next(s for s in elec["segments"] if s["month"] == month)
    assert segment["tariff"]["tariffKind"] == "TOU"
    # 기본요금 = 300kW × 8,320원
    assert segment["basicCharge"] == "2496000"
    # 요율이 모든 시각에 100원이라 사용량 × 100과 같아야 한다.
    expected = (Decimal(segment["usage"]) * 100).quantize(Decimal(1))
    assert Decimal(segment["usageCharge"]) == expected
    bands = {b["loadBand"]: b for b in segment["loadBands"]}
    assert Decimal(bands["MID"]["charge"]) == expected
    assert Decimal(bands["PEAK"]["charge"]) == 0


# ---------- 부하 패턴·피크 ----------


def test_load_pattern_profiles_by_day_kind_and_hour(fems):
    client, _, _ = fems
    data = _ok(client.get(f"{F}/load-pattern"))
    assert data["source"]["sourceCode"] == "ELEC"
    assert data["profile"], "시드 계측이 있어야 한다"
    keys = [(r["dayKind"], r["hour"]) for r in data["profile"]]
    assert len(keys) == len(set(keys)), "요일 구분·시각마다 한 줄"
    assert all(r["dayKind"] in tou.DAY_KINDS for r in data["profile"])
    assert all(0 <= r["hour"] <= 23 for r in data["profile"])
    assert all(Decimal(r["average"]) <= Decimal(r["max"]) for r in data["profile"])


def test_peak_is_the_hourly_maximum_and_knows_it_is_an_approximation(fems):
    client, _, _ = fems
    data = _ok(client.get(f"{F}/load-pattern"))
    peak = data["peak"]
    assert peak and Decimal(peak["value"]) > 0
    assert 0 <= peak["hour"] <= 23
    # 계약전력이 없는 FLAT 요금제라 비율은 0이 아니라 모름이다.
    assert peak["contractKw"] is None and peak["contractRatio"] is None

    highest = max(Decimal(r["max"]) for r in data["profile"])
    assert Decimal(peak["value"]) == highest


def test_peak_ratio_appears_once_a_contract_power_exists(fems):
    client, created, _ = fems
    data = _ok(client.get(f"{F}/load-pattern"))
    month = data["month"]
    tariff = _make_current_tariff_tou(client, created, month)
    _ok(
        client.put(
            f"{F}/tariffs/{tariff['id']}/bands",
            json={"bands": _full_bands()},
            headers=_headers(created),
        )
    )
    after = _ok(client.get(f"{F}/load-pattern?month={month}"))
    assert after["peak"]["contractKw"] == "300.00"
    assert Decimal(after["peak"]["contractRatio"]) > 0


def test_base_load_is_the_night_minimum(fems):
    client, _, _ = fems
    data = _ok(client.get(f"{F}/load-pattern"))
    base = data["baseLoad"]
    assert base and base["hours"] == "0~6"
    assert Decimal(base["value"]) <= Decimal(base["average"])
