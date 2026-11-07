"""BEMS 읽기 전용 조회 인터페이스 (FS-013 §6 · FS-029 D46·D48 · DSN-21 Q4).

CMMS가 BEMS를 이 모듈로만 읽는다 — 공조기를 설비 대장으로 가져오고, **환경 경보**를
작업지시 전환 대기 신호로 쓴다. 전환해도 BEMS 쪽 경보 상태는 바뀌지 않는다(해제는 BEMS가 한다).
BEMS를 꺼 두었으면 None을 돌려주고, CMMS는 그 출처 없이 동작한다.

경보는 **환경 경보(온도·습도·CO2)만** 있다. 설비 경보는 DSN-21 Q4에서 CMMS 신호로 쓰지 않기로 했다.
호출자의 범위(scoped: 활성 세대가 확정된 AuthContext)로만 조회한다.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """BEMS 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return module_available(connection, scoped.workspace_id, "bems")


def hvac_units(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """사용 중인 공조기 `[{code, name, zoneCode, zoneName, ratedKw}]`. BEMS가 꺼져 있으면 None.

    CMMS가 설비 대장(종류 HVAC)으로 가져온다. 코드만 스냅샷으로 넘기고 FK는 걸지 않는다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT h.code, h.name, z.code zone_code, z.name zone_name, h.rated_kw "
            "FROM bems.hvac_unit h "
            "JOIN bems.zone z ON z.workspace_id=h.workspace_id "
            " AND z.generation_id=h.generation_id AND z.id=h.zone_id "
            "WHERE h.workspace_id=:w AND h.generation_id=:g AND h.is_active "
            "ORDER BY h.code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "code": row["code"],
            "name": row["name"],
            "zoneCode": row["zone_code"],
            "zoneName": row["zone_name"],
            "ratedKw": str(row["rated_kw"]),
        }
        for row in rows
    ]


def active_alarms(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """해제되지 않은 환경 경보. BEMS가 꺼져 있으면 None.

    CMMS가 전환 대기 신호로 읽어 고장 작업지시를 만든다(D48, 신호 1건당 작업지시 1건).
    확인(acknowledged)했어도 해제 전이면 여전히 대상이다 — 확인은 '봤다'일 뿐 조치가 아니다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT a.id, a.status, a.raised_at, a.peak_value, r.metric, r.comparator, "
            " r.threshold, r.severity, s.code sensor_code, z.code zone_code, z.name zone_name "
            "FROM bems.alarm a "
            "JOIN bems.alarm_rule r ON r.workspace_id=a.workspace_id "
            " AND r.generation_id=a.generation_id AND r.id=a.alarm_rule_id "
            "JOIN bems.sensor s ON s.workspace_id=a.workspace_id "
            " AND s.generation_id=a.generation_id AND s.id=a.sensor_id "
            "JOIN bems.zone z ON z.workspace_id=s.workspace_id "
            " AND z.generation_id=s.generation_id AND z.id=s.zone_id "
            "WHERE a.workspace_id=:w AND a.generation_id=:g AND a.status <> 'cleared' "
            "ORDER BY a.raised_at DESC, a.id DESC"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "alarmId": str(row["id"]),
            "status": row["status"],
            "metric": row["metric"],
            "comparator": row["comparator"],
            "threshold": str(row["threshold"]),
            "severity": row["severity"],
            "peakValue": str(row["peak_value"]),
            "sensorCode": row["sensor_code"],
            "zoneCode": row["zone_code"],
            "zoneName": row["zone_name"],
            "raisedAt": row["raised_at"].isoformat(),
        }
        for row in rows
    ]


def monthly_summary(
    connection: Connection, scoped: AuthContext, month: str
) -> dict[str, Any] | None:
    """지표 키 → 값 (DSN-90 2-1 공통). **확정한** 월간 건물 보고서의 최신 버전만 읽는다.

    EIP 경영 요약이 읽는다. 초안·대체된 버전은 주지 않는다. 확정본이 없으면 지표 값이 모두 None이다
    (0으로 보이면 '쓰지 않았다'와 '아직 안 만들었다'가 섞인다). BEMS가 꺼져 있으면 None.
    """
    if not enabled(connection, scoped):
        return None
    row = (
        connection.execute(
            text(
                "SELECT total_kwh, eui_kwh_m2, total_cost, target_achievement, comfort_ratio "
                "FROM bems.energy_review WHERE workspace_id=:w AND generation_id=:g "
                " AND review_month=:month AND status='confirmed' "
                "ORDER BY version DESC LIMIT 1"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "month": month},
        )
        .mappings()
        .first()
    )

    def value(key: str) -> str | None:
        return None if row is None or row[key] is None else str(Decimal(row[key]))

    return {
        "month": month,
        "metrics": {
            "commonKwh": value("total_kwh"),
            "euiKwhPerM2": value("eui_kwh_m2"),
            "commonCost": value("total_cost"),
            "targetAchievement": value("target_achievement"),
            "comfortRatio": value("comfort_ratio"),
        },
    }
