"""FEMS 읽기 전용 조회 인터페이스 (FS-023 D9 · X1~X6, FS-025 7장).

다른 솔루션(BEMS)은 FEMS를 이 모듈로만 읽는다. 반환은 값(dict/list)이며 행을 잠그지 않는다.
FEMS를 꺼 두었으면 None을 돌려주고, 호출 쪽은 분해만 "계산 불가"로 줄여 동작한다(D12).
기준은 FEMS 화면과 같다 — 사업장 합계 = F-01·F-04의 최상위 계측기, 제조 = F-03의 DIRECT_METER 배분.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available
from fs.fems import repository as repo
from fs.fems import tou


def _s(scoped: AuthContext) -> dict[str, int]:
    return {"w": scoped.workspace_id, "g": scoped.generation_id}


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """FEMS 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return module_available(connection, scoped.workspace_id, "fems")


def site_electricity(
    connection: Connection, scoped: AuthContext, date_from: date, date_to: date
) -> dict[str, Decimal] | None:
    """사업장 전력(kWh) 일별 합 `{YYYY-MM-DD: kWh}` — 최상위 전력 계측기, 결측 제외. FEMS 꺼짐이면 None."""
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT to_char((r.observed_at - interval '1 microsecond') AT TIME ZONE s.timezone,'YYYY-MM-DD') reading_day,"
            "coalesce(sum(r.value*c.multiplier) FILTER (WHERE r.quality<>'invalid'),0) kwh "
            + repo.READING_FROM
            + repo.READING_PERIOD
            + " AND m.parent_meter_id IS NULL AND e.source_kind='ELECTRIC' AND c.unit='kWh'"
            " GROUP BY reading_day"
        ),
        {**_s(scoped), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return {r["reading_day"]: r["kwh"] for r in rows}


def manufacturing_electricity(
    connection: Connection, scoped: AuthContext, date_from: date, date_to: date
) -> dict[str, Decimal] | None:
    """제조 전력(kWh) 일별 합 `{YYYY-MM-DD: kWh}` — 설비 직접 계측 배분(현재 결과, 결측 제외). FEMS 꺼짐이면 None."""
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT to_char(x.period_start AT TIME ZONE x.timezone,'YYYY-MM-DD') reading_day, sum(x.quantity) kwh "
            f"FROM ({repo.ALLOCATION_BASE}) x "
            "WHERE x.is_latest AND x.quality<>'invalid' AND x.method_key='DIRECT_METER' AND x.unit='kWh' "
            "GROUP BY reading_day"
        ),
        {**_s(scoped), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return {r["reading_day"]: r["kwh"] for r in rows}


def open_alarms(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """진행 중인 에너지 경보 `[{ruleCode, alarmKind, equipmentCode, peakValue, status}]`.

    BEMS 피크 감축이 PEAK 경보를 읽는다(DSN-15 6장). **CMMS 작업지시 신호로는 쓰지 않는다**
    — 에너지 이상은 고장이 아니다(DSN-21 Q4로 제외). FEMS가 꺼져 있으면 None.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT r.code rule_code, r.name rule_name, r.alarm_kind, r.threshold, r.unit,"
            " e.equipment_code, c.channel_code, a.peak_value, a.status, a.raised_at "
            "FROM fems.alarm a "
            "JOIN fems.alarm_rule r ON r.workspace_id=a.workspace_id "
            " AND r.generation_id=a.generation_id AND r.id=a.alarm_rule_id "
            "LEFT JOIN fems.equipment e ON e.workspace_id=r.workspace_id "
            " AND e.generation_id=r.generation_id AND e.id=r.equipment_id "
            "LEFT JOIN fems.meter_channel c ON c.workspace_id=r.workspace_id "
            " AND c.generation_id=r.generation_id AND c.id=r.meter_channel_id "
            "WHERE a.workspace_id=:w AND a.generation_id=:g AND a.status <> 'CLEARED' "
            "ORDER BY a.raised_at DESC"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "ruleCode": r["rule_code"],
            "ruleName": r["rule_name"],
            "alarmKind": r["alarm_kind"],
            "threshold": str(r["threshold"]),
            "unit": r["unit"],
            "equipmentCode": r["equipment_code"],
            "channelCode": r["channel_code"],
            "peakValue": str(r["peak_value"]),
            "status": r["status"],
            "raisedAt": r["raised_at"].isoformat(),
        }
        for r in rows
    ]


def energy_costs(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]] | None:
    """**확정한** 월 에너지 비용 배분 `[{equipmentCode, departmentCode, itemCode, sourceCode, quantity, unit, cost}]`.

    ERP 원가 화면이 **참고로** 읽는다(DSN-15 Q4) — ERP의 원가 배부 기준은 생산량 그대로이고 이것으로
    바꾸지 않는다. 초안·대체된 버전은 주지 않는다. 확정본이 없으면 빈 목록, FEMS가 꺼져 있으면 None.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT q.equipment_code, l.department_code, l.item_code, s.source_code,"
            " l.quantity, l.unit, l.cost "
            "FROM fems.cost_run r "
            "JOIN fems.cost_allocation_line l ON l.workspace_id=r.workspace_id "
            " AND l.generation_id=r.generation_id AND l.cost_run_id=r.id "
            "JOIN fems.equipment q ON q.workspace_id=l.workspace_id "
            " AND q.generation_id=l.generation_id AND q.id=l.equipment_id "
            "JOIN fems.energy_source s ON s.workspace_id=l.workspace_id "
            " AND s.generation_id=l.generation_id AND s.id=l.energy_source_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g "
            " AND r.cost_month=:month AND r.status='confirmed' "
            "ORDER BY q.equipment_code, s.source_code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "month": month},
    ).mappings()
    return [
        {
            "equipmentCode": r["equipment_code"],
            "departmentCode": r["department_code"],
            "itemCode": r["item_code"],
            "sourceCode": r["source_code"],
            "quantity": str(r["quantity"]),
            "unit": r["unit"],
            "cost": str(r["cost"]),
        }
        for r in rows
    ]


def tariff_rates(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]] | None:
    """그 달 **전력** 요금제의 시간별 단가 `[{sourceCode, unit, tariffCode, kind, contractKw, basicCharge, rates}]`.

    `rates`는 `{YYYY-MM-DD: [0시~23시 단가 24개]}`(사업장 시간대 기준 시각). 계절·요일 구분·휴일 달력은
    FEMS 요금 산정과 같은 규칙으로 여기서 풀어 준다 — BEMS가 TOU 구간표를 따로 해석하지 않게 한다.
    FLAT은 24칸이 모두 같은 사용 단가이고, 구간표에 없는 시각은 FEMS 요금 산정처럼 0이다.
    `basicCharge`는 단가가 아니라 **기본요금 단가**(계약전력당, FLAT은 고정액)라 쓰는 쪽이 정한다.
    그 달 요금제가 없는 전력원은 빠진다. FEMS가 꺼져 있으면 None.
    """
    if not enabled(connection, scoped):
        return None
    last_day = monthrange(int(month[:4]), int(month[5:7]))[1]
    first, last = (
        date(int(month[:4]), int(month[5:7]), 1),
        date(int(month[:4]), int(month[5:7]), last_day),
    )
    holiday_days = repo.holidays(connection, scoped, first, last)
    result = []
    for source in connection.execute(
        text(
            "SELECT id, source_code, measure_unit FROM fems.energy_source "
            "WHERE workspace_id=:w AND generation_id=:g AND source_kind='ELECTRIC' "
            " AND is_billable AND is_active ORDER BY source_code"
        ),
        _s(scoped),
    ).mappings():
        tariff = (
            connection.execute(
                text(
                    f"SELECT {repo.TARIFF_COLUMNS} FROM fems.tariff "
                    "WHERE workspace_id=:w AND generation_id=:g AND energy_source_id=:source "
                    " AND effective_from <= :month AND (effective_to IS NULL OR effective_to >= :month) "
                    "ORDER BY effective_from DESC, id DESC LIMIT 1"
                ),
                {**_s(scoped), "source": source["id"], "month": month},
            )
            .mappings()
            .first()
        )
        if tariff is None:
            continue
        table = (
            tou.rate_lookup(
                repo.tariff_bands(connection, scoped, [tariff["id"]])[tariff["id"]]
            )
            if tariff["tariff_kind"] == "TOU"
            else None
        )
        rates = {}
        for offset in range(last_day):
            day = first.replace(day=offset + 1)
            kind = tou.day_kind_of(day, holiday_days)
            season = tou.season_of(day.month)
            rates[day.isoformat()] = [
                str(
                    tariff["usage_rate"]
                    if table is None
                    else table[(season, kind, hour)]["rate"]
                    if (season, kind, hour) in table
                    else Decimal(0)
                )
                for hour in range(tou.HOURS_IN_DAY)
            ]
        result.append(
            {
                "sourceCode": source["source_code"],
                "unit": source["measure_unit"],
                "tariffCode": tariff["tariff_code"],
                "kind": tariff["tariff_kind"],
                "contractKw": None
                if tariff["contract_kw"] is None
                else str(tariff["contract_kw"]),
                "basicCharge": str(tariff["basic_charge"]),
                "rates": rates,
            }
        )
    return result
