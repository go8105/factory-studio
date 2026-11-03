"""FEMS 읽기 전용 조회 인터페이스 (FS-023 D9 · X1~X6, FS-025 7장).

다른 솔루션(BEMS)은 FEMS를 이 모듈로만 읽는다. 반환은 값(dict/list)이며 행을 잠그지 않는다.
FEMS를 꺼 두었으면 None을 돌려주고, 호출 쪽은 분해만 "계산 불가"로 줄여 동작한다(D12).
기준은 FEMS 화면과 같다 — 사업장 합계 = F-01·F-04의 최상위 계측기, 제조 = F-03의 DIRECT_METER 배분.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available
from fs.fems import repository as repo


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
