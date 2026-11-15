"""BEMS 업무 규칙 (FS-025 모듈 설계 3·5·6장).

- 공용 계측·환경 관측은 1시간 구간, 불변. 과거는 시드, 이후는 "1시간 진행"(TX-B2)이 만든다.
- 분해(D20): 잔여 = FEMS 사업장 전력 − FEMS 제조 전력 − BEMS 공용 전력. FEMS는 fs.fems.interface로만 읽는다(D9).
  잔여가 음수면 숨기지 않고 불일치로 표시한다. 저장하지 않는다.
- 공조(D21): 모의 공조기 상태는 제어 명령(TX-B1)과 스케줄 경계 전환으로만 바뀐다. 설정값은 명령 이력의 마지막 적용값이다.
- 경보(D22): 규칙 조건이 지속 시간 동안 참이면 발생, 1시간 거짓이면 해제, 확인은 사람만(TX-B3).

쓰기는 write_scope의 공간 잠금 뒤에 실행되므로 진행·명령이 공간 안에서 직렬화된다.
"""

from __future__ import annotations

import re
from calendar import monthrange
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import ROUND_CEILING, Decimal
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from fs.bems import simulation as sim
from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.core import interface as core
from fs.fems import interface as fems
from fs.hr import interface as hr

MODULE = "bems"
SEOUL = ZoneInfo("Asia/Seoul")
_S = "workspace_id=:w AND generation_id=:g"
UNITS = {
    "TEMP": "℃",
    "HUMIDITY": "%",
    "CO2": "ppm",
    "PM25": "㎍/㎥",
    "LUX": "lx",
    "OCCUPANCY": "명",
}


# ---------- 공통 ----------


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


# 공통 엔진: 조회 트랜잭션(REPEATABLE READ · 읽기 전용)
_read = read


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row(row: Any) -> dict[str, Any]:
    return {_camel(k): _value(v) for k, v in row.items()}


def _fields(fields: dict[str, str]) -> ApiError:
    return ApiError(
        400, "VALIDATION_FAILED", "입력값을 확인해 주세요.", {"fields": fields}
    )


def _conflict(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


def _not_found(label: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{label}을(를) 찾을 수 없습니다.")


Action = Callable[[Connection, AuthContext], tuple[Any, str, int]]


# 공통 엔진(fs.common.engine.action): 공간 잠금 → 멱등 영수증 → 처리 → 영수증 저장
_action = partial(action, MODULE)


def _one(connection, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    row = connection.execute(text(sql), params).mappings().first()
    return None if row is None else _row(row)


def _all(connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [_row(r) for r in connection.execute(text(sql), params).mappings()]


# ---------- 기준정보 (B-07) ----------

MASTER = {
    "building": ("건물", "code, name, floors, gross_area_m2, is_active", "code"),
    "zone": (
        "구역",
        "code, name, kind, floor_area_m2, is_active, building_id, floor_label, department_code",
        "code",
    ),
    "meter": ("공용 계측기", "zone_id, code, name, usage, unit, is_active", "code"),
    "sensor": ("환경 센서", "zone_id, code, metric, unit, is_active", "code"),
    "hvac_unit": (
        "공조기",
        "zone_id, code, name, meter_id, rated_kw, state, control_source, state_changed_at, is_active, curtail_priority",
        "code",
    ),
    "lighting_circuit": (
        "조명 회로",
        "zone_id, code, name, meter_id, rated_kw, state, control_source, state_changed_at, is_active",
        "code",
    ),
    "comfort_standard": (
        "쾌적 기준",
        "zone_kind, metric, low, high, occupied_only",
        "zone_kind, metric",
    ),
    "equipment_alarm_rule": (
        "설비 경보 규칙",
        "code, condition, hvac_unit_id, threshold, severity, is_active",
        "code",
    ),
    "energy_target": (
        "건물 에너지 목표",
        "target_month, zone_id, target_kwh",
        "target_month DESC, zone_id NULLS FIRST",
    ),
}
# zone_id 칼럼이 없는 기준정보. 구역으로 거르지 않는다.
NO_ZONE = frozenset({"zone", "building", "comfort_standard", "equipment_alarm_rule"})


def _master(connection, scoped, table: str, row_id: int) -> dict[str, Any] | None:
    columns = MASTER[table][1]
    return _one(
        connection,
        f"SELECT id, {columns} FROM bems.{table} WHERE {_S} AND id=:id",
        {**_s(scoped), "id": row_id},
    )


def list_master(
    context: AuthContext, table: str, zone_id: int | None = None
) -> list[dict[str, Any]]:
    _, columns, order = MASTER[table]
    where = " AND zone_id=:z" if zone_id and table not in NO_ZONE else ""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            f"SELECT id, {columns} FROM bems.{table} WHERE {_S}{where} ORDER BY {order}",
            {**_s(scoped), "z": zone_id},
        )


def _check_refs(connection, scoped, table: str, values: dict[str, Any]) -> None:
    errors: dict[str, str] = {}
    if (
        values.get("zone_id") is not None
        and _master(connection, scoped, "zone", values["zone_id"]) is None
    ):
        errors["zoneId"] = "구역을 고르세요."
    if (
        table in ("hvac_unit", "lighting_circuit")
        and values.get("meter_id") is not None
    ):
        meter = _master(connection, scoped, "meter", values["meter_id"])
        zone = values.get("zone_id")
        usage = "HVAC" if table == "hvac_unit" else "LIGHTING"
        if (
            meter is None
            or meter["usage"] != usage
            or (zone and meter["zoneId"] != zone)
        ):
            errors["meterId"] = (
                "같은 구역의 "
                + ("공조" if usage == "HVAC" else "조명")
                + " 용도 계측기만 고를 수 있습니다."
            )
    if table == "zone":
        errors.update(_check_zone_place(connection, scoped, values))
    if (
        table == "equipment_alarm_rule"
        and values.get("hvac_unit_id") is not None
        and _master(connection, scoped, "hvac_unit", values["hvac_unit_id"]) is None
    ):
        errors["hvacUnitId"] = "공조기를 고르세요."
    if errors:
        raise _fields(errors)


FLOOR_ABOVE = re.compile(r"^([1-9]\d{0,2})F$")


def _check_comfort_range(values: dict[str, Any]) -> None:
    """하한·상한 중 적어도 하나는 있어야 하고, 둘 다면 하한 < 상한이다(DB CHECK보다 먼저 본다)."""
    low, high = values.get("low"), values.get("high")
    if low is None and high is None:
        raise _fields({"low": "하한과 상한 중 하나는 입력하세요."})
    if low is not None and high is not None and Decimal(low) >= Decimal(high):
        raise _fields({"high": "상한은 하한보다 커야 합니다."})


def _check_zone_place(connection, scoped, values: dict[str, Any]) -> dict[str, str]:
    """건물·층·부서. 층 표기는 건물이 있어야 하고 지상층 번호는 건물 층수를 넘을 수 없다."""
    errors: dict[str, str] = {}
    building = None
    if values.get("building_id") is not None:
        building = _master(connection, scoped, "building", values["building_id"])
        if building is None:
            errors["buildingId"] = "건물을 고르세요."
    if values.get("floor_label") is not None:
        if values.get("building_id") is None:
            errors["floorLabel"] = "건물을 먼저 고르세요."
        elif building is not None:
            above = FLOOR_ABOVE.match(values["floor_label"])
            if above and int(above.group(1)) > building["floors"]:
                errors["floorLabel"] = f"이 건물은 {building['floors']}층까지입니다."
    code = values.get("department_code")
    if code is not None:
        # 부서 코드는 HR이 원천이다. HR을 껐으면 목록이 없어 형식만 본다(FEMS 설비와 같은 규칙).
        rows = hr.departments(connection, scoped)
        if rows is not None and code not in {r["code"] for r in rows}:
            errors["departmentCode"] = "HR에 없는 부서 코드입니다."
    return errors


def list_departments(context: AuthContext) -> dict[str, Any]:
    """구역에 붙일 부서 후보. HR이 꺼져 있으면 목록이 아니라 꺼졌다고 답한다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = hr.departments(connection, scoped)
    if rows is None:
        return {"hrEnabled": False, "rows": []}
    return {
        "hrEnabled": True,
        "rows": [{"code": r["code"], "name": r["name"]} for r in rows if r["isActive"]],
    }


def create_master(
    context: AuthContext, table: str, values: dict[str, Any], key: str
) -> dict[str, Any]:

    def fn(connection, scoped):
        if (
            "code" in values
            and connection.execute(
                text(f"SELECT 1 FROM bems.{table} WHERE {_S} AND code=:c"),
                {**_s(scoped), "c": values["code"]},
            ).first()
        ):
            raise _fields({"code": "이미 사용 중인 코드입니다."})
        if table == "comfort_standard":
            _check_comfort_range(values)
        if (
            table == "energy_target"
            and connection.execute(
                text(
                    f"SELECT 1 FROM bems.energy_target WHERE {_S} AND target_month=:m "
                    "AND zone_id IS NOT DISTINCT FROM :z"
                ),
                {**_s(scoped), "m": values["target_month"], "z": values.get("zone_id")},
            ).first()
        ):
            raise _fields({"targetMonth": "이 달의 같은 범위 목표가 이미 있습니다."})
        if (
            table == "comfort_standard"
            and connection.execute(
                text(
                    f"SELECT 1 FROM bems.comfort_standard WHERE {_S} AND zone_kind=:k AND metric=:m"
                ),
                {**_s(scoped), "k": values["zone_kind"], "m": values["metric"]},
            ).first()
        ):
            raise _fields({"metric": "이 용도에는 같은 지표의 기준이 이미 있습니다."})
        row = dict(values)
        if table == "sensor":
            row["unit"] = UNITS[row["metric"]]
            if connection.execute(
                text(
                    f"SELECT 1 FROM bems.sensor WHERE {_S} AND zone_id=:z AND metric=:m"
                ),
                {**_s(scoped), "z": row["zone_id"], "m": row["metric"]},
            ).first():
                raise _fields(
                    {"metric": "이 구역에는 같은 항목의 센서가 이미 있습니다."}
                )
        _check_refs(connection, scoped, table, row)
        columns = ", ".join(row)
        binds = ", ".join(f":{k}" for k in row)
        row_id = connection.execute(
            text(
                f"INSERT INTO bems.{table}(workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {binds}) RETURNING id"
            ),
            {**_s(scoped), **row},
        ).scalar_one()
        return _master(connection, scoped, table, row_id), table, row_id

    return _action(context, f"bems.{table}.create", key, values, fn, 201)


def update_master(
    context: AuthContext, table: str, row_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def fn(connection, scoped):
        found = _master(connection, scoped, table, row_id)
        if found is None:
            raise _not_found(MASTER[table][0])
        if table in ("hvac_unit", "lighting_circuit") and "meter_id" in values:
            _check_refs(
                connection, scoped, table, {**values, "zone_id": found["zoneId"]}
            )
        if table == "zone" and {"building_id", "floor_label", "department_code"} & set(
            values
        ):
            merged = {
                "building_id": found["buildingId"],
                "floor_label": found["floorLabel"],
                **values,
            }
            # 바꾸지 않은 부서 코드는 다시 검사하지 않는다(HR에서 사라진 옛 코드도 그대로 둘 수 있다).
            merged["department_code"] = values.get("department_code")
            errors = _check_zone_place(connection, scoped, merged)
            if errors:
                raise _fields(errors)
        if table == "comfort_standard":
            _check_comfort_range(
                {
                    "low": found["low"],
                    "high": found["high"],
                    **{k: v for k, v in values.items() if k in ("low", "high")},
                }
            )
        if (
            table == "building"
            and values.get("is_active") is False
            and connection.execute(
                text(
                    f"SELECT 1 FROM bems.zone WHERE {_S} AND building_id=:b AND is_active LIMIT 1"
                ),
                {**_s(scoped), "b": row_id},
            ).first()
        ):
            raise _conflict(
                "사용 중인 구역이 있는 건물은 사용 안 함으로 바꿀 수 없습니다.",
                "BUILDING_HAS_ACTIVE_ZONES",
            )
        sets = ", ".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE bems.{table} SET {sets} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": row_id},
        )
        return _master(connection, scoped, table, row_id), table, row_id

    return _action(context, f"bems.{table}.update:{row_id}", key, values, fn)


# ---------- 관측 조회 (B-03) ----------


def _period(
    date_from: date | None, date_to: date | None, days: int = 2
) -> tuple[datetime, datetime]:
    """[시작, 끝) KST 자정 경계. 기본은 업무 기준일까지 최근 N일."""
    end_day = (date_to or business_today()) + timedelta(days=1)
    start_day = date_from or end_day - timedelta(days=days)
    return datetime.combine(start_day, time(), SEOUL), datetime.combine(
        end_day, time(), SEOUL
    )


def environment(
    context: AuthContext, zone_id: int, date_from: date | None, date_to: date | None
) -> dict[str, Any]:
    start, end = _period(date_from, date_to)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if _master(connection, scoped, "zone", zone_id) is None:
            raise _not_found("구역")
        rows = _all(
            connection,
            "SELECT r.period_start, s.metric, r.value, r.quality, r.source FROM bems.environment_reading r "
            "JOIN bems.sensor s ON s.workspace_id=r.workspace_id AND s.generation_id=r.generation_id AND s.id=r.sensor_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g AND s.zone_id=:z AND r.period_start>=:a AND r.period_start<:b "
            "ORDER BY r.period_start, s.metric",
            {**_s(scoped), "z": zone_id, "a": start, "b": end},
        )
        setpoints = {
            k: str(v) for k, v in _setpoints(connection, scoped, zone_id).items()
        }
        return {"zoneId": zone_id, "readings": rows, "setpoints": setpoints}


def energy(
    context: AuthContext,
    meter_id: int | None,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, Any]]:
    start, end = _period(date_from, date_to)
    where = " AND r.meter_id=:m" if meter_id else ""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            "SELECT r.period_start, r.meter_id, m.code meter_code, m.usage, r.value, r.quality, r.source "
            "FROM bems.energy_reading r JOIN bems.meter m ON m.workspace_id=r.workspace_id "
            "AND m.generation_id=r.generation_id AND m.id=r.meter_id "
            f"WHERE r.workspace_id=:w AND r.generation_id=:g AND r.period_start>=:a AND r.period_start<:b{where} "
            "ORDER BY r.period_start, m.code",
            {**_s(scoped), "m": meter_id, "a": start, "b": end},
        )


# ---------- 에너지 분해 (B-02, D20) ----------


def _common_by_day(
    connection, scoped, start: datetime, end: datetime
) -> tuple[dict[str, dict[str, Decimal]], dict[str, int]]:
    usage: dict[str, dict[str, Decimal]] = {}
    hours: dict[str, int] = {}
    for r in connection.execute(
        text(
            "SELECT to_char(r.period_start AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD') reading_day, m.usage, "
            "sum(r.value) FILTER (WHERE r.quality='valid') kwh, count(*) FILTER (WHERE r.quality='valid') n "
            "FROM bems.energy_reading r JOIN bems.meter m ON m.workspace_id=r.workspace_id "
            "AND m.generation_id=r.generation_id AND m.id=r.meter_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.period_start>=:a AND r.period_start<:b "
            "GROUP BY reading_day, m.usage"
        ),
        {**_s(scoped), "a": start, "b": end},
    ).mappings():
        usage.setdefault(r["reading_day"], {})[r["usage"]] = r["kwh"] or Decimal(0)
        hours[r["reading_day"]] = hours.get(r["reading_day"], 0) + r["n"]
    return usage, hours


def breakdown(
    context: AuthContext, granularity: str, date_from: date | None, date_to: date | None
) -> dict[str, Any]:
    last = date_to or business_today() - timedelta(days=1)
    first = date_from or last - timedelta(days=29)
    start, end = _period(first, last)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        site = fems.site_electricity(connection, scoped, first, last)
        if site is None:
            raise _conflict(
                "FEMS를 사용하지 않도록 설정했습니다. 공용 계측·공조 운전은 그대로 쓸 수 있습니다.",
                "SOURCE_MODULE_DISABLED",
                sourceModule="fems",
            )
        made = fems.manufacturing_electricity(connection, scoped, first, last) or {}
        common, hours = _common_by_day(connection, scoped, start, end)
        meters = connection.execute(
            text(f"SELECT count(*) FROM bems.meter WHERE {_S} AND is_active"),
            _s(scoped),
        ).scalar_one()
    days = sorted(set(site) | set(common))
    buckets: dict[str, dict[str, Any]] = {}
    for day in days:
        key = day[:7] if granularity == "month" else day
        b = buckets.setdefault(
            key,
            {
                "period": key,
                "site": Decimal(0),
                "manufacturing": Decimal(0),
                "common": {},
                "missingHours": 0,
            },
        )
        b["site"] += site.get(day, Decimal(0))
        b["manufacturing"] += made.get(day, Decimal(0))
        for usage, kwh in common.get(day, {}).items():
            b["common"][usage] = b["common"].get(usage, Decimal(0)) + kwh
        b["missingHours"] += max(0, meters * 24 - hours.get(day, 0))
    rows = []
    for b in buckets.values():
        common_total = sum(b["common"].values(), Decimal(0))
        residual = b["site"] - b["manufacturing"] - common_total
        rows.append(
            {
                "period": b["period"],
                "site": str(b["site"]),
                "manufacturing": str(b["manufacturing"]),
                "common": str(common_total),
                "commonByUsage": {k: str(v) for k, v in sorted(b["common"].items())},
                "residual": str(residual),
                "mismatch": residual < 0,
                "missingHours": b["missingHours"],
            }
        )
    return {
        "granularity": granularity,
        "from": first.isoformat(),
        "to": last.isoformat(),
        "rows": rows,
    }


# ---------- 공조 운전 (B-04·B-05, TX-B1) ----------


def _setpoints(connection, scoped, zone_id: int) -> dict[str, Decimal]:
    current = dict(sim.DEFAULT_SETPOINTS)
    for r in connection.execute(
        text(
            f"SELECT DISTINCT ON (setpoint_kind) setpoint_kind, value FROM bems.control_command "
            f"WHERE {_S} AND zone_id=:z AND command='SET_SETPOINT' AND result='APPLIED' "
            "ORDER BY setpoint_kind, requested_at DESC, id DESC"
        ),
        {**_s(scoped), "z": zone_id},
    ).mappings():
        current[r["setpoint_kind"]] = r["value"]
    return current


def day_kind(connection, scoped, day: date) -> str:
    """요일 구분. 휴일(core 달력) > 토·일 > 평일(DSN-16 Q1)."""
    if core.holidays(connection, scoped, day, day):
        return "HOLIDAY"
    return "WEEKDAY" if day.weekday() < 5 else "WEEKEND"


# 스케줄 대상(공조기·조명 회로)별 FK 열. 이름은 상수라 SQL에 직접 넣는다.
TARGET = {"hvac_unit": "hvac_unit_id", "lighting_circuit": "lighting_circuit_id"}


def _scheduled_mode(
    connection, scoped, unit_id: int, moment: datetime, table: str = "hvac_unit"
) -> str:
    """그 시각의 스케줄 모드(조명 회로는 ON). 없으면 OFF.

    휴일에 그 대상의 휴일 시간대가 하나도 없으면 주말 시간대를 따른다 — 휴일 칸을 비워 두면
    '휴일은 주말처럼'이다. 하루 종일 끄려면 휴일 시간대를 아예 두지 않은 채 주말도 비운다.
    """
    column = TARGET[table]
    local = moment.astimezone(SEOUL)
    kind = day_kind(connection, scoped, local.date())
    if (
        kind == "HOLIDAY"
        and not connection.execute(
            text(
                f"SELECT 1 FROM bems.schedule_slot WHERE {_S} AND {column}=:u AND is_active "
                "AND day_kind='HOLIDAY' LIMIT 1"
            ),
            {**_s(scoped), "u": unit_id},
        ).first()
    ):
        kind = "WEEKEND"
    mode = connection.execute(
        text(
            f"SELECT mode FROM bems.schedule_slot WHERE {_S} AND {column}=:u AND is_active "
            "AND day_kind=:k AND start_hour<=:h AND end_hour>:h ORDER BY start_hour LIMIT 1"
        ),
        {**_s(scoped), "u": unit_id, "k": kind, "h": local.hour},
    ).scalar()
    return mode or "OFF"


COMMAND_SQL = f"""
SELECT c.id, c.zone_id, c.hvac_unit_id, h.code hvac_code, c.lighting_circuit_id, l.code lighting_code,
       c.demand_plan_id, c.command, c.mode, c.setpoint_kind, c.value, c.source,
       c.requested_at, c.result, c.reject_reason, c.note
FROM bems.control_command c
LEFT JOIN bems.hvac_unit h ON h.workspace_id=c.workspace_id AND h.generation_id=c.generation_id AND h.id=c.hvac_unit_id
LEFT JOIN bems.lighting_circuit l ON l.workspace_id=c.workspace_id AND l.generation_id=c.generation_id AND l.id=c.lighting_circuit_id
WHERE c.{_S.replace(" AND ", " AND c.")}
"""


def hvac_units(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        units = list_master_in(connection, scoped, "hvac_unit")
        latest = _latest_environment(connection, scoped)
        power = {
            r["meter_id"]: str(r["value"])
            for r in connection.execute(
                text(
                    f"SELECT DISTINCT ON (meter_id) meter_id, value FROM bems.energy_reading WHERE {_S} "
                    "ORDER BY meter_id, period_start DESC"
                ),
                _s(scoped),
            ).mappings()
        }
        for u in units:
            u["setpoints"] = {
                k: str(v)
                for k, v in _setpoints(connection, scoped, u["zoneId"]).items()
            }
            u["environment"] = latest.get(u["zoneId"], {})
            u["lastPower"] = power.get(u["meterId"])
        return units


def list_master_in(connection, scoped, table: str) -> list[dict[str, Any]]:
    return _all(
        connection,
        f"SELECT id, {MASTER[table][1]} FROM bems.{table} WHERE {_S} ORDER BY {MASTER[table][2]}",
        _s(scoped),
    )


def hvac_unit(context: AuthContext, unit_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        unit = _master(connection, scoped, "hvac_unit", unit_id)
        if unit is None:
            raise _not_found("공조기")
        unit["setpoints"] = {
            k: str(v) for k, v in _setpoints(connection, scoped, unit["zoneId"]).items()
        }
        unit["commands"] = _all(
            connection,
            COMMAND_SQL
            + " AND (c.hvac_unit_id=:u OR (c.hvac_unit_id IS NULL AND c.lighting_circuit_id IS NULL AND c.zone_id=:z)) "
            "ORDER BY c.requested_at DESC, c.id DESC LIMIT 20",
            {**_s(scoped), "u": unit_id, "z": unit["zoneId"]},
        )
        unit["schedule"] = _schedule(connection, scoped, unit_id)
        return unit


def commands(
    context: AuthContext,
    zone_id: int | None,
    unit_id: int | None,
    circuit_id: int | None = None,
) -> list[dict[str, Any]]:
    where = ""
    if zone_id:
        where += " AND c.zone_id=:z"
    if unit_id:
        where += " AND c.hvac_unit_id=:u"
    if circuit_id:
        where += " AND c.lighting_circuit_id=:l"
    elif not unit_id:
        # 공조 화면의 이력에 조명 명령이 섞이지 않게 한다. 조명은 회로를 지정해 본다.
        where += " AND c.lighting_circuit_id IS NULL"
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            COMMAND_SQL + where + " ORDER BY c.requested_at DESC, c.id DESC LIMIT 200",
            {**_s(scoped), "z": zone_id, "u": unit_id, "l": circuit_id},
        )


def _insert_command(
    connection, scoped, values: dict[str, Any], at: datetime | None = None
) -> int:
    return connection.execute(
        text(
            "INSERT INTO bems.control_command(workspace_id,generation_id,zone_id,hvac_unit_id,lighting_circuit_id,demand_plan_id,"
            "command,mode,setpoint_kind,value,source,requested_at,result,reject_reason,note) VALUES "
            "(:w,:g,:zone_id,:hvac_unit_id,:lighting_circuit_id,:demand_plan_id,"
            ":command,:mode,:setpoint_kind,:value,:source,"
            "COALESCE(CAST(:at AS timestamptz), clock_timestamp()),:result,:reject_reason,:note) RETURNING id"
        ),
        {
            **_s(scoped),
            "hvac_unit_id": None,
            "lighting_circuit_id": None,
            "demand_plan_id": None,
            "mode": None,
            "setpoint_kind": None,
            "value": None,
            "reject_reason": None,
            "note": None,
            **values,
            "at": at,
        },
    ).scalar_one()


def _set_state(
    connection,
    scoped,
    unit_id: int,
    state: str,
    source: str,
    at: datetime | None = None,
    table: str = "hvac_unit",
) -> None:
    connection.execute(
        text(
            f"UPDATE bems.{table} SET state=:s, control_source=:src, "
            f"state_changed_at=COALESCE(CAST(:at AS timestamptz), clock_timestamp()) WHERE {_S} AND id=:id"
        ),
        {**_s(scoped), "s": state, "src": source, "id": unit_id, "at": at},
    )


def send_command(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """TX-B1. 거부도 이력으로 남기고 사유를 돌려준다(201)."""

    def fn(connection, scoped):
        zone = _master(connection, scoped, "zone", values["zone_id"])
        if zone is None:
            raise _fields({"zoneId": "구역을 고르세요."})
        command = values["command"]
        row = {
            "zone_id": zone["id"],
            "command": command,
            "source": "MANUAL",
            "note": values.get("note"),
        }
        reason = None
        unit = None
        circuit = None
        if values.get("lighting_circuit_id") is not None:
            if command not in ("POWER_ON", "POWER_OFF"):
                raise _fields({"command": "조명 회로는 켜기·끄기만 할 수 있습니다."})
            if values.get("hvac_unit_id") is not None:
                raise _fields(
                    {"hvacUnitId": "공조기와 조명 회로를 함께 고를 수 없습니다."}
                )
            circuit = _master(
                connection, scoped, "lighting_circuit", values["lighting_circuit_id"]
            )
            if circuit is None or circuit["zoneId"] != zone["id"]:
                raise _fields({"lightingCircuitId": "이 구역의 조명 회로를 고르세요."})
            row["lighting_circuit_id"] = circuit["id"]
            if not circuit["isActive"]:
                reason = "UNIT_INACTIVE"
            elif command == "POWER_OFF" and circuit["state"] == "OFF":
                reason = "ALREADY_OFF"
            elif command == "POWER_ON" and circuit["state"] == "ON":
                reason = "ALREADY_ON"
        elif command == "SET_SETPOINT":
            kind, value = values.get("setpoint_kind"), values.get("value")
            if kind is None or value is None:
                raise _fields({"value": "설정값 항목과 값을 입력하세요."})
            value = Decimal(value)
            row.update(
                setpoint_kind=kind, value=value, hvac_unit_id=values.get("hvac_unit_id")
            )
            reason = sim.setpoint_error(
                kind, value, _setpoints(connection, scoped, zone["id"])
            )
        else:
            unit = _master(
                connection, scoped, "hvac_unit", values.get("hvac_unit_id") or 0
            )
            if unit is None or unit["zoneId"] != zone["id"]:
                raise _fields({"hvacUnitId": "이 구역의 공조기를 고르세요."})
            row["hvac_unit_id"] = unit["id"]
            if not unit["isActive"]:
                reason = "UNIT_INACTIVE"
            elif command == "POWER_OFF" and unit["state"] == "OFF":
                reason = "ALREADY_OFF"
            elif command == "POWER_ON" and unit["state"] != "OFF":
                reason = "ALREADY_ON"
            elif command == "SET_MODE":
                if values.get("mode") is None:
                    raise _fields({"mode": "모드를 고르세요."})
                row["mode"] = values["mode"]
                if unit["state"] == values["mode"]:
                    reason = "SAME_STATE"
        row.update(result="REJECTED" if reason else "APPLIED", reject_reason=reason)
        # 수동 명령도 시뮬레이션 시계(다음 구간 시작)로 기록해 스케줄 명령·관측과 한 시간축에 놓는다.
        now = _simulation_clock(connection, scoped)[0]
        command_id = _insert_command(connection, scoped, row, now)
        if not reason and circuit is not None:
            _set_state(
                connection,
                scoped,
                circuit["id"],
                "ON" if command == "POWER_ON" else "OFF",
                "MANUAL",
                now,
                "lighting_circuit",
            )
        if not reason and unit is not None:
            if command == "POWER_ON":
                # 켜면 시뮬레이션 현재 시각의 스케줄 모드로, 스케줄이 없는 시간이면 송풍으로 운전한다.
                planned = _scheduled_mode(connection, scoped, unit["id"], now)
                state = planned if planned != "OFF" else "FAN"
            else:
                state = "OFF" if command == "POWER_OFF" else row["mode"]
            _set_state(connection, scoped, unit["id"], state, "MANUAL", now)
        result = _one(
            connection, COMMAND_SQL + " AND c.id=:id", {**_s(scoped), "id": command_id}
        )
        return result, "control_command", command_id

    return _action(context, "bems.command", key, values, fn, 201)


def _schedule(
    connection, scoped, unit_id: int, table: str = "hvac_unit"
) -> list[dict[str, Any]]:
    return _all(
        connection,
        f"SELECT id, day_kind, start_hour, end_hour, mode, is_active FROM bems.schedule_slot "
        f"WHERE {_S} AND {TARGET[table]}=:u "
        "ORDER BY CASE day_kind WHEN 'WEEKDAY' THEN 1 WHEN 'WEEKEND' THEN 2 ELSE 3 END, start_hour",
        {**_s(scoped), "u": unit_id},
    )


def _replace_schedule(
    context: AuthContext,
    table: str,
    unit_id: int,
    slots: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    column = TARGET[table]
    lighting = table == "lighting_circuit"
    errors: dict[str, str] = {}
    for i, a in enumerate(slots):
        if (a["mode"] == "ON") != lighting:
            errors[f"slots.{i}"] = (
                "조명 회로는 켜짐(ON) 시간대만 둡니다."
                if lighting
                else "공조기는 냉방·난방·송풍 중에서 고르세요."
            )
            continue
        if a["start_hour"] >= a["end_hour"]:
            errors[f"slots.{i}"] = "종료 시각이 시작보다 늦어야 합니다."
            continue
        for j, b in enumerate(slots[:i]):
            if (
                a["day_kind"] == b["day_kind"]
                and a["start_hour"] < b["end_hour"]
                and b["start_hour"] < a["end_hour"]
            ):
                errors[f"slots.{i}"] = f"{j + 1}번째 시간대와 겹칩니다."
    if errors:
        raise _fields(errors)

    def fn(connection, scoped):
        if _master(connection, scoped, table, unit_id) is None:
            raise _not_found("조명 회로" if lighting else "공조기")
        connection.execute(
            text(f"DELETE FROM bems.schedule_slot WHERE {_S} AND {column}=:u"),
            {**_s(scoped), "u": unit_id},
        )
        for slot in slots:
            connection.execute(
                text(
                    f"INSERT INTO bems.schedule_slot(workspace_id,generation_id,{column},day_kind,start_hour,end_hour,mode) "
                    "VALUES (:w,:g,:u,:day_kind,:start_hour,:end_hour,:mode)"
                ),
                {**_s(scoped), "u": unit_id, **slot},
            )
        return _schedule(connection, scoped, unit_id, table), table, unit_id

    return _action(
        context, f"bems.schedule:{table}:{unit_id}", key, {"slots": slots}, fn
    )


def replace_schedule(
    context: AuthContext, unit_id: int, slots: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    return _replace_schedule(context, "hvac_unit", unit_id, slots, key)


def replace_lighting_schedule(
    context: AuthContext, circuit_id: int, slots: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    return _replace_schedule(context, "lighting_circuit", circuit_id, slots, key)


def lighting_circuit(context: AuthContext, circuit_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        circuit = _master(connection, scoped, "lighting_circuit", circuit_id)
        if circuit is None:
            raise _not_found("조명 회로")
        circuit["commands"] = _all(
            connection,
            COMMAND_SQL
            + " AND c.lighting_circuit_id=:l ORDER BY c.requested_at DESC, c.id DESC LIMIT 20",
            {**_s(scoped), "l": circuit_id},
        )
        circuit["schedule"] = _schedule(
            connection, scoped, circuit_id, "lighting_circuit"
        )
        return circuit


# ---------- 1시간 진행 (TX-B2, D21) ----------


def _latest_environment(connection, scoped) -> dict[int, dict[str, str]]:
    latest: dict[int, dict[str, str]] = {}
    for r in connection.execute(
        text(
            "SELECT DISTINCT ON (s.id) s.zone_id, s.metric, r.value FROM bems.environment_reading r "
            "JOIN bems.sensor s ON s.workspace_id=r.workspace_id AND s.generation_id=r.generation_id AND s.id=r.sensor_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g ORDER BY s.id, r.period_start DESC"
        ),
        _s(scoped),
    ).mappings():
        latest.setdefault(r["zone_id"], {})[r["metric"]] = str(r["value"])
    return latest


def _simulation_clock(connection, scoped) -> tuple[datetime, datetime]:
    """(다음 구간 시작, 한도). 한도 = 업무 기준일 다음 날 00:00(KST) — 그 전 구간까지만 만든다."""
    last = connection.execute(
        text(
            f"SELECT greatest((SELECT max(period_start) FROM bems.environment_reading WHERE {_S}),"
            f"(SELECT max(period_start) FROM bems.energy_reading WHERE {_S}))"
        ),
        _s(scoped),
    ).scalar()
    limit = datetime.combine(business_today() + timedelta(days=1), time(), SEOUL)
    start = (
        (last + timedelta(hours=1)).astimezone(SEOUL)
        if last
        else datetime.combine(business_today(), time(), SEOUL)
    )
    return start, limit


def _step(connection, scoped, moment: datetime) -> dict[str, int]:
    local = moment.astimezone(SEOUL)
    # 휴일(core 달력)에는 사람이 없다 — 평일 재실 모델은 평일에만 쓴다.
    weekday = day_kind(connection, scoped, local.date()) == "WEEKDAY"
    summary = {"readings": 0, "switches": 0, "raised": 0, "cleared": 0}
    units = list_master_in(connection, scoped, "hvac_unit")
    previous = moment - timedelta(hours=1)
    for table, targets in (
        ("hvac_unit", units),
        ("lighting_circuit", list_master_in(connection, scoped, "lighting_circuit")),
    ):
        for u in targets:
            if not u["isActive"]:
                continue
            planned = _scheduled_mode(connection, scoped, u["id"], moment, table)
            boundary = planned != _scheduled_mode(
                connection, scoped, u["id"], previous, table
            )
            if (u["controlSource"] == "SCHEDULE" or boundary) and (
                u["state"] != planned or u["controlSource"] != "SCHEDULE"
            ):
                if table == "lighting_circuit":
                    command, mode = (
                        ("POWER_ON" if planned == "ON" else "POWER_OFF"),
                        None,
                    )
                else:
                    command = (
                        "POWER_OFF"
                        if planned == "OFF"
                        else ("POWER_ON" if u["state"] == "OFF" else "SET_MODE")
                    )
                    mode = planned if command == "SET_MODE" else None
                _insert_command(
                    connection,
                    scoped,
                    {
                        "zone_id": u["zoneId"],
                        "hvac_unit_id": u["id"] if table == "hvac_unit" else None,
                        "lighting_circuit_id": u["id"]
                        if table == "lighting_circuit"
                        else None,
                        "command": command,
                        "mode": mode,
                        "source": "SCHEDULE",
                        "result": "APPLIED",
                    },
                    moment,
                )
                _set_state(
                    connection, scoped, u["id"], planned, "SCHEDULE", moment, table
                )
                u["state"], u["controlSource"] = planned, "SCHEDULE"
                summary["switches"] += 1
    latest = _latest_environment(connection, scoped)
    zones = list_master_in(connection, scoped, "zone")
    state_by_zone = {u["zoneId"]: u["state"] for u in units if u["isActive"]}
    # 조도는 그 구역 조명 회로가 하나라도 켜져 있는지로 정한다.
    lit_zones = {
        c["zoneId"]
        for c in list_master_in(connection, scoped, "lighting_circuit")
        if c["isActive"] and c["state"] == "ON"
    }
    temps: dict[int, Decimal] = {}
    for z in zones:
        # 관측 이력이 없는 센서(새로 등록)는 시작값에서 출발한다.
        values = {**sim.start_values(local.hour), **latest.get(z["id"], {})}
        state = state_by_zone.get(z["id"], "OFF")
        setpoints = _setpoints(connection, scoped, z["id"])
        nxt = {}
        if "TEMP" in values:
            nxt["TEMP"] = sim.next_temperature(
                Decimal(values["TEMP"]), local.hour, state, setpoints
            )
            temps[z["id"]] = nxt["TEMP"]
        if "HUMIDITY" in values:
            nxt["HUMIDITY"] = sim.next_humidity(Decimal(values["HUMIDITY"]), state)
        occupied = sim.occupancy(local.hour, weekday, z["kind"]) > 0
        if "CO2" in values:
            nxt["CO2"] = sim.next_co2(
                Decimal(values["CO2"]),
                local.hour,
                weekday,
                z["kind"] == "OFFICE",
                state,
            )
        if "PM25" in values:
            nxt["PM25"] = sim.next_pm25(Decimal(values["PM25"]), occupied, state)
        # 조도·재실은 누적이 아니라 그 시각의 상태에서 바로 나온다.
        nxt["LUX"] = sim.lux(local.hour, z["id"] in lit_zones)
        nxt["OCCUPANCY"] = sim.occupancy(local.hour, weekday, z["kind"])
        for metric, value in nxt.items():
            summary["readings"] += connection.execute(
                text(
                    "INSERT INTO bems.environment_reading(workspace_id,generation_id,sensor_id,period_start,value,source) "
                    f"SELECT :w,:g,id,:t,:v,'SIMULATION' FROM bems.sensor WHERE {_S} AND zone_id=:z AND metric=:m AND is_active "
                    "ON CONFLICT DO NOTHING"
                ),
                {**_s(scoped), "t": moment, "v": value, "z": z["id"], "m": metric},
            ).rowcount
    hvac_kwh: dict[int, Decimal] = {}
    for u in units:
        if u["meterId"] and u["isActive"]:
            setpoints = _setpoints(connection, scoped, u["zoneId"])
            temp = temps.get(u["zoneId"], setpoints["COOL_TEMP"])
            hvac_kwh[u["meterId"]] = hvac_kwh.get(
                u["meterId"], Decimal(0)
            ) + sim.hvac_power(u["state"], Decimal(u["ratedKw"]), temp, setpoints)
    for m in list_master_in(connection, scoped, "meter"):
        if not m["isActive"]:
            continue
        value = (
            hvac_kwh.get(m["id"], Decimal(0))
            if m["usage"] == "HVAC"
            else sim.fixed_load(m["usage"], local.hour, weekday)
        )
        summary["readings"] += connection.execute(
            text(
                "INSERT INTO bems.energy_reading(workspace_id,generation_id,meter_id,period_start,value,source) "
                "VALUES (:w,:g,:m,:t,:v,'SIMULATION') ON CONFLICT DO NOTHING"
            ),
            {**_s(scoped), "m": m["id"], "t": moment, "v": value},
        ).rowcount
    for evaluate in (_evaluate_alarms, _evaluate_equipment_alarms):
        raised, cleared = evaluate(connection, scoped, moment)
        summary["raised"] += raised
        summary["cleared"] += cleared
    return summary


def _evaluate_alarms(connection, scoped, moment: datetime) -> tuple[int, int]:
    raised = cleared = 0
    rules = _all(
        connection,
        f"SELECT r.id, r.zone_id, r.metric, r.comparator, r.threshold, r.duration_hours, s.id sensor_id "
        f"FROM bems.alarm_rule r JOIN bems.sensor s ON s.workspace_id=r.workspace_id AND s.generation_id=r.generation_id "
        f"AND s.zone_id=r.zone_id AND s.metric=r.metric WHERE r.{_S.replace(' AND ', ' AND r.')} AND r.is_active",
        _s(scoped),
    )
    for rule in rules:
        values = [
            v
            for (v,) in connection.execute(
                text(
                    f"SELECT value FROM bems.environment_reading WHERE {_S} AND sensor_id=:s AND period_start<=:t "
                    "ORDER BY period_start DESC LIMIT :n"
                ),
                {
                    **_s(scoped),
                    "s": rule["sensorId"],
                    "t": moment,
                    "n": rule["durationHours"],
                },
            )
        ]
        threshold = Decimal(rule["threshold"])
        high = rule["comparator"] == "HIGH"
        hits = [v > threshold if high else v < threshold for v in values]
        open_alarm = _one(
            connection,
            f"SELECT id, peak_value FROM bems.alarm WHERE {_S} AND alarm_rule_id=:r AND sensor_id=:s AND status<>'cleared'",
            {**_s(scoped), "r": rule["id"], "s": rule["sensorId"]},
        )
        if open_alarm is None:
            if len(values) == rule["durationHours"] and all(hits):
                peak = max(values) if high else min(values)
                connection.execute(
                    text(
                        "INSERT INTO bems.alarm(workspace_id,generation_id,alarm_rule_id,sensor_id,raised_at,peak_value) "
                        "VALUES (:w,:g,:r,:s,:t,:p) ON CONFLICT DO NOTHING"
                    ),
                    {
                        **_s(scoped),
                        "r": rule["id"],
                        "s": rule["sensorId"],
                        "t": moment,
                        "p": peak,
                    },
                )
                raised += 1
        elif values and not hits[0]:
            connection.execute(
                text(
                    f"UPDATE bems.alarm SET status='cleared', cleared_at=:t WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "t": moment, "id": open_alarm["id"]},
            )
            cleared += 1
        elif values:
            peak = Decimal(open_alarm["peakValue"])
            better = max(peak, values[0]) if high else min(peak, values[0])
            connection.execute(
                text(f"UPDATE bems.alarm SET peak_value=:p WHERE {_S} AND id=:id"),
                {**_s(scoped), "p": better, "id": open_alarm["id"]},
            )
    return raised, cleared


# ---------- 건물 에너지·공용 비용·월간 보고서 (B-11~B-13, DSN-16 F41~F44·Q6) ----------
#
# 원단위(EUI) = 공용 kWh ÷ 연면적. 저장하지 않고 조회로 계산한다(보고서를 확정할 때만 스냅샷으로 남는다).
# 달성률 = 실적 ÷ 목표다(FEMS와 같은 규칙: 100% 이하면 목표 이내).
# 공용 비용 = 시간별 공용 사용량 × 그 시각 FEMS 전력 단가. FEMS가 꺼져 있으면 **계산을 거부한다** —
# 요율을 모르면 부분 합계가 확정본에 남기 때문이다.

RATIO4 = Decimal("0.0001")
MONEY = Decimal("0.01")


def _month_range(month: str) -> tuple[datetime, datetime, date, date]:
    first = date(int(month[:4]), int(month[5:7]), 1)
    last = date(first.year, first.month, monthrange(first.year, first.month)[1])
    start = datetime.combine(first, time(), SEOUL)
    end = datetime.combine(last + timedelta(days=1), time(), SEOUL)
    return start, end, first, last


def _common_hourly(connection, scoped, start, end) -> list[dict[str, Any]]:
    """공용 계측 시간별 합 `[{day, hour, zone_id, kwh}]`. 품질이 valid인 것만 센다."""
    return _all(
        connection,
        "SELECT to_char(r.period_start AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD') \"day\", "
        "CAST(to_char(r.period_start AT TIME ZONE 'Asia/Seoul','HH24') AS integer) \"hour\", "
        "m.zone_id, sum(r.value) kwh "
        "FROM bems.energy_reading r JOIN bems.meter m ON m.workspace_id=r.workspace_id "
        " AND m.generation_id=r.generation_id AND m.id=r.meter_id "
        f"WHERE r.{_S.replace(' AND ', ' AND r.')} AND r.quality='valid' "
        'AND r.period_start>=:a AND r.period_start<:b GROUP BY "day", "hour", m.zone_id',
        {**_s(scoped), "a": start, "b": end},
    )


def _gross_area(connection, scoped) -> Decimal:
    """건물 연면적 합. 건물이 없으면 구역 면적 합으로 대신한다."""
    buildings = [
        Decimal(b["grossAreaM2"])
        for b in list_master_in(connection, scoped, "building")
        if b["isActive"]
    ]
    if buildings:
        return sum(buildings, Decimal(0))
    return sum(
        (
            Decimal(z["floorAreaM2"])
            for z in list_master_in(connection, scoped, "zone")
            if z["isActive"] and z["floorAreaM2"]
        ),
        Decimal(0),
    )


def _targets(connection, scoped, month: str) -> dict[int | None, Decimal]:
    return {
        t["zoneId"]: Decimal(t["targetKwh"])
        for t in list_master_in(connection, scoped, "energy_target")
        if t["targetMonth"] == month
    }


def _achievement(actual: Decimal, target: Decimal | None) -> str | None:
    """달성률 = 실적 ÷ 목표(FEMS와 같다). 목표가 없으면 0이 아니라 모름이다."""
    if not target:
        return None
    return str((actual / target).quantize(RATIO4))


def building_energy(context: AuthContext, month: str | None) -> dict[str, Any]:
    """B-11. 그 달 공용 사용량·원단위·목표 달성률을 건물 전체와 구역별로 본다."""
    month = month or business_today().strftime("%Y-%m")
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        start, end, _, _ = _month_range(month)
        rows = _common_hourly(connection, scoped, start, end)
        zones = {z["id"]: z for z in list_master_in(connection, scoped, "zone")}
        targets = _targets(connection, scoped, month)
        by_zone: dict[int, Decimal] = {}
        for r in rows:
            by_zone[r["zoneId"]] = by_zone.get(r["zoneId"], Decimal(0)) + Decimal(
                r["kwh"]
            )
        total = sum(by_zone.values(), Decimal(0))
        area = _gross_area(connection, scoped)
        return {
            "month": month,
            "totalKwh": str(total.quantize(MONEY)),
            "grossAreaM2": str(area.quantize(MONEY)),
            # 연면적이 0이면 원단위를 0으로 적지 않는다 — 나눌 수 없는 것이다.
            "euiKwhPerM2": None if not area else str((total / area).quantize(RATIO4)),
            "targetKwh": None if None not in targets else str(targets[None]),
            "achievement": _achievement(total, targets.get(None)),
            "zones": [
                {
                    "zoneId": zone_id,
                    "zoneCode": zones[zone_id]["code"],
                    "zoneName": zones[zone_id]["name"],
                    "kind": zones[zone_id]["kind"],
                    "floorAreaM2": zones[zone_id]["floorAreaM2"],
                    "kwh": str(kwh.quantize(MONEY)),
                    "euiKwhPerM2": None
                    if not zones[zone_id]["floorAreaM2"]
                    else str(
                        (kwh / Decimal(zones[zone_id]["floorAreaM2"])).quantize(RATIO4)
                    ),
                    "targetKwh": None
                    if zone_id not in targets
                    else str(targets[zone_id]),
                    "achievement": _achievement(kwh, targets.get(zone_id)),
                }
                for zone_id, kwh in sorted(by_zone.items())
                if zone_id in zones
            ],
        }


# ---- 공용 비용 배분 (B-12) ----

COST_SQL = f"""
SELECT id, cost_month, version, status, total_kwh, total_cost, currency, confirmed_at
FROM bems.cost_run WHERE {_S}
"""


def _cost_lines(connection, scoped, run_id: int) -> list[dict[str, Any]]:
    return _all(
        connection,
        "SELECT id, department_code, area_m2, share, cost, currency FROM bems.cost_allocation_line "
        f"WHERE {_S} AND cost_run_id=:r ORDER BY department_code",
        {**_s(scoped), "r": run_id},
    )


def _cost_run(connection, scoped, run_id: int) -> dict[str, Any] | None:
    run = _one(connection, COST_SQL + " AND id=:id", {**_s(scoped), "id": run_id})
    if run is not None:
        run["lines"] = _cost_lines(connection, scoped, run_id)
    return run


def _hourly_cost(connection, scoped, month: str, rows) -> Decimal:
    """시간별 공용 사용량 × 그 시각 전력 단가. 요금제가 없으면 계산을 거부한다."""
    rates = fems.tariff_rates(connection, scoped, month)
    if rates is None:
        raise _conflict(
            "FEMS를 사용하지 않도록 설정해 전력 단가를 읽을 수 없습니다.",
            "SOURCE_MODULE_DISABLED",
            sourceModule="fems",
        )
    if not rates:
        raise _conflict(
            "그 달 전력 요금제가 없어 공용 비용을 계산할 수 없습니다.", "NO_TARIFF"
        )
    # 전력원이 여럿이면 첫 요금제를 쓴다(공용 계측은 모두 전력이다).
    table = rates[0]["rates"]
    total = Decimal(0)
    for r in rows:
        day = table.get(r["day"])
        if day is None:
            continue
        total += Decimal(r["kwh"]) * Decimal(day[r["hour"]])
    return total.quantize(MONEY)


def _department_areas(connection, scoped) -> dict[str, Decimal]:
    areas: dict[str, Decimal] = {}
    for zone in list_master_in(connection, scoped, "zone"):
        code, area = zone["departmentCode"], zone["floorAreaM2"]
        if not zone["isActive"] or not code or not area:
            continue
        areas[code] = areas.get(code, Decimal(0)) + Decimal(area)
    return areas


def cost_runs(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection, COST_SQL + " ORDER BY cost_month DESC, version DESC", _s(scoped)
        )


def cost_run(context: AuthContext, run_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _cost_run(connection, scoped, run_id)
        if found is None:
            raise _not_found("비용 배분")
        return found


def calculate_cost(context: AuthContext, month: str, key: str) -> dict[str, Any]:
    """그 달 공용 비용을 계산해 초안을 만든다. 같은 달의 옛 초안은 지운다(작업 중인 계산이다)."""

    def fn(connection, scoped):
        start, end, _, _ = _month_range(month)
        rows = _common_hourly(connection, scoped, start, end)
        if not rows:
            raise _conflict("그 달 공용 계측이 없습니다.", "NO_READINGS")
        areas = _department_areas(connection, scoped)
        if not areas:
            raise _conflict(
                "부서를 지정한 구역이 없어 배분할 수 없습니다. 구역·계측에서 사용 부서를 정하세요.",
                "NO_DEPARTMENT_AREA",
            )
        total_kwh = sum((Decimal(r["kwh"]) for r in rows), Decimal(0)).quantize(MONEY)
        total_cost = _hourly_cost(connection, scoped, month, rows)
        connection.execute(
            text(
                f"DELETE FROM bems.cost_run WHERE {_S} AND cost_month=:m AND status='draft'"
            ),
            {**_s(scoped), "m": month},
        )
        version = connection.execute(
            text(
                f"SELECT COALESCE(max(version),0)+1 FROM bems.cost_run WHERE {_S} AND cost_month=:m"
            ),
            {**_s(scoped), "m": month},
        ).scalar_one()
        run_id = connection.execute(
            text(
                "INSERT INTO bems.cost_run(workspace_id,generation_id,cost_month,version,total_kwh,total_cost) "
                "VALUES (:w,:g,:m,:v,:k,:c) RETURNING id"
            ),
            {**_s(scoped), "m": month, "v": version, "k": total_kwh, "c": total_cost},
        ).scalar_one()
        area_sum = sum(areas.values(), Decimal(0))
        assigned = Decimal(0)
        codes = sorted(areas)
        for index, code in enumerate(codes):
            share = (areas[code] / area_sum).quantize(Decimal("0.000001"))
            # 마지막 줄이 끝수를 떠안아 줄의 합이 총액과 정확히 같아진다.
            cost = (
                total_cost - assigned
                if index == len(codes) - 1
                else (total_cost * share).quantize(MONEY)
            )
            assigned += cost
            connection.execute(
                text(
                    "INSERT INTO bems.cost_allocation_line(workspace_id,generation_id,cost_run_id,"
                    "department_code,area_m2,share,cost) VALUES (:w,:g,:r,:code,:area,:share,:cost)"
                ),
                {
                    **_s(scoped),
                    "r": run_id,
                    "code": code,
                    "area": areas[code],
                    "share": share,
                    "cost": cost,
                },
            )
        return _cost_run(connection, scoped, run_id), "cost_run", run_id

    return _action(context, f"bems.cost.calculate:{month}", key, {}, fn, 201)


def _confirm_snapshot(connection, scoped, table: str, column: str, row_id: int) -> None:
    """초안을 확정한다. 같은 기간의 기존 확정본은 superseded로 넘긴다(새 버전이 이긴다)."""
    params = {**_s(scoped), "id": row_id}
    connection.execute(
        text(
            f"UPDATE bems.{table} SET status='superseded' WHERE {_S} AND status='confirmed' "
            f"AND {column}=(SELECT {column} FROM bems.{table} WHERE {_S} AND id=:id)"
        ),
        params,
    )
    connection.execute(
        text(
            f"UPDATE bems.{table} SET status='confirmed', confirmed_at=now() WHERE {_S} AND id=:id"
        ),
        params,
    )


def confirm_cost(context: AuthContext, run_id: int, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        found = _cost_run(connection, scoped, run_id)
        if found is None:
            raise _not_found("비용 배분")
        if found["status"] != "draft":
            raise _conflict(
                "초안만 확정할 수 있습니다.", "BAD_STATE", status=found["status"]
            )
        _confirm_snapshot(connection, scoped, "cost_run", "cost_month", run_id)
        return _cost_run(connection, scoped, run_id), "cost_run", run_id

    return _action(context, f"bems.cost.confirm:{run_id}", key, {}, fn)


# ---- 월간 건물 보고서 (B-13) ----

REVIEW_SQL = f"""
SELECT id, review_month, version, status, total_kwh, eui_kwh_m2 AS eui_kwh_per_m2, target_achievement,
       total_cost, currency, comfort_ratio, issues, confirmed_at
FROM bems.energy_review WHERE {_S}
"""


def reviews(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            REVIEW_SQL + " ORDER BY review_month DESC, version DESC",
            _s(scoped),
        )


def review(context: AuthContext, review_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _one(
            connection, REVIEW_SQL + " AND id=:id", {**_s(scoped), "id": review_id}
        )
        if found is None:
            raise _not_found("월간 보고서")
        return found


def _month_comfort(context: AuthContext, month: str) -> str | None:
    """그 달 쾌적 시간 비율(전 구역·지표 합산). 셀 관측이 없으면 모름이다."""
    _, _, first, last = _month_range(month)
    rows = comfort(context, first, last)["rows"]
    hours = sum(r["hours"] for r in rows)
    if not hours:
        return None
    inside = sum(r["insideHours"] for r in rows)
    return str((Decimal(inside) / Decimal(hours)).quantize(RATIO4))


def draft_review(
    context: AuthContext, month: str, issues: str | None, key: str
) -> dict[str, Any]:
    """월간 보고서 초안. 비용은 **확정한 배분**만 가져온다(초안 비용을 보고서에 싣지 않는다)."""
    comfort_ratio = _month_comfort(context, month)

    def fn(connection, scoped):
        start, end, _, _ = _month_range(month)
        rows = _common_hourly(connection, scoped, start, end)
        if not rows:
            raise _conflict("그 달 공용 계측이 없습니다.", "NO_READINGS")
        total_kwh = sum((Decimal(r["kwh"]) for r in rows), Decimal(0)).quantize(MONEY)
        area = _gross_area(connection, scoped)
        if not area:
            raise _conflict(
                "건물 연면적이 없어 원단위를 낼 수 없습니다. 건물을 먼저 등록하세요.",
                "NO_AREA",
            )
        confirmed = _one(
            connection,
            COST_SQL + " AND cost_month=:m AND status='confirmed'",
            {**_s(scoped), "m": month},
        )
        connection.execute(
            text(
                f"DELETE FROM bems.energy_review WHERE {_S} AND review_month=:m AND status='draft'"
            ),
            {**_s(scoped), "m": month},
        )
        version = connection.execute(
            text(
                f"SELECT COALESCE(max(version),0)+1 FROM bems.energy_review WHERE {_S} AND review_month=:m"
            ),
            {**_s(scoped), "m": month},
        ).scalar_one()
        review_id = connection.execute(
            text(
                "INSERT INTO bems.energy_review(workspace_id,generation_id,review_month,version,"
                "total_kwh,eui_kwh_m2,target_achievement,total_cost,comfort_ratio,issues) "
                "VALUES (:w,:g,:m,:v,:k,:e,:a,:c,:r,:i) RETURNING id"
            ),
            {
                **_s(scoped),
                "m": month,
                "v": version,
                "k": total_kwh,
                "e": (total_kwh / area).quantize(RATIO4),
                "a": _achievement(
                    total_kwh, _targets(connection, scoped, month).get(None)
                ),
                "c": Decimal(confirmed["totalCost"]) if confirmed else Decimal(0),
                "r": comfort_ratio,
                "i": issues,
            },
        ).scalar_one()
        result = _one(
            connection, REVIEW_SQL + " AND id=:id", {**_s(scoped), "id": review_id}
        )
        return result, "energy_review", review_id

    return _action(
        context, f"bems.review.draft:{month}", key, {"issues": issues}, fn, 201
    )


def confirm_review(context: AuthContext, review_id: int, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        found = _one(
            connection, REVIEW_SQL + " AND id=:id", {**_s(scoped), "id": review_id}
        )
        if found is None:
            raise _not_found("월간 보고서")
        if found["status"] != "draft":
            raise _conflict(
                "초안만 확정할 수 있습니다.", "BAD_STATE", status=found["status"]
            )
        _confirm_snapshot(
            connection, scoped, "energy_review", "review_month", review_id
        )
        result = _one(
            connection, REVIEW_SQL + " AND id=:id", {**_s(scoped), "id": review_id}
        )
        return result, "energy_review", review_id

    return _action(context, f"bems.review.confirm:{review_id}", key, {}, fn)


# ---------- 피크 감축 (B-09, DSN-16 F24·Q2) ----------
#
# FEMS 진행 PEAK 경보 1건당 감축안 1건. **자동 제어는 하지 않는다**(Q2) —
# 서버가 감축안을 계산해 두고, 담당자가 승인할 때 비로소 제어 명령(출처 PEAK)이 나간다.
# 경보가 해제된 뒤 복귀를 승인하면 각 공조기를 스케줄 운전으로 되돌린다.
#
# 공조기의 control_source는 'SCHEDULE'·'MANUAL'뿐이라(1a CHECK) 감축 중에는 MANUAL로 둔다.
# 수동 명령과 같은 규칙이므로 감축은 다음 스케줄 경계까지 유지된다.

PEAK_ACTIONS = ("RAISE_SETPOINT", "SET_FAN", "POWER_OFF")
PLAN_SQL = f"""
SELECT id, plan_no, fems_alarm_ref, proposed_at, target_reduction_kw, status,
       decided_at, executed_at, restored_at, decision_note
FROM bems.demand_plan WHERE {_S}
"""


def _peak_alarms(connection, scoped) -> list[dict[str, Any]] | None:
    """FEMS 진행 피크 경보. FEMS가 꺼져 있으면 None(0건과 구분한다)."""
    alarms = fems.open_alarms(connection, scoped)
    if alarms is None:
        return None
    return [a for a in alarms if a["alarmKind"] == "PEAK"]


def _alarm_ref(alarm: dict[str, Any]) -> str:
    """경보 1건을 가리키는 코드 스냅샷. FEMS로 FK를 두지 않는다(FS-013 §6)."""
    return f"{alarm['ruleCode']}@{alarm['raisedAt'][:16]}"


def _over_kw(connection, scoped, alarm: dict[str, Any]) -> Decimal | None:
    """감축할 양(kW) = 측정 피크 − 한계. **PEAK 규칙의 한계값은 kW가 아니라 계약전력 대비 비율**이라
    계약전력을 알아야 kW가 나온다(FEMS `tariff_rates`). 계약전력이 없으면 0이 아니라 **모름**이다."""
    rates = fems.tariff_rates(connection, scoped, alarm["raisedAt"][:7]) or []
    contract = next((r["contractKw"] for r in rates if r["contractKw"]), None)
    if contract is None:
        return None
    limit = Decimal(alarm["threshold"]) * Decimal(contract)
    return (Decimal(alarm["peakValue"]) - limit).quantize(sim.Q2)


def _zone_temperature(connection, scoped, zone_id: int, cool: Decimal) -> Decimal:
    latest = _latest_environment(connection, scoped).get(zone_id, {})
    return Decimal(latest["TEMP"]) if "TEMP" in latest else cool


def _curtail_step(
    unit: dict[str, Any],
    temp: Decimal,
    setpoints: dict[str, Decimal],
    remaining: Decimal,
) -> dict[str, Any] | None:
    """공조기 한 대에서 뽑을 단계. 모자란 만큼만 완화한 동작으로 고르고, 없으면 더 센 동작으로 올린다."""
    rated = Decimal(unit["ratedKw"])
    now = sim.hvac_power(unit["state"], rated, temp, setpoints)
    if now <= 0:
        return None
    options: list[tuple[str, Decimal, Decimal | None]] = []
    if unit["state"] == "COOL":
        # 필요한 만큼만 올린다(0.5 단위, 0.5~5℃). 상향 1℃당 감축은 정격 × LOAD_PER_DEGREE다.
        per_degree = rated * sim.LOAD_PER_DEGREE
        steps = (remaining / per_degree * 2).to_integral_value(
            rounding=ROUND_CEILING
        ) / 2
        delta = min(Decimal(5), max(Decimal("0.5"), steps))
        raised = {**setpoints, "COOL_TEMP": setpoints["COOL_TEMP"] + delta}
        options.append(
            ("RAISE_SETPOINT", now - sim.hvac_power("COOL", rated, temp, raised), delta)
        )
    if unit["state"] in ("COOL", "HEAT"):
        options.append(("SET_FAN", now - rated * sim.FAN_SHARE, None))
    options.append(("POWER_OFF", now, None))
    for name, saving, delta in options:
        if saving >= remaining and saving > 0:
            return {
                "action": name,
                "expected_kw": saving.quantize(sim.Q2),
                "delta_value": delta,
            }
    name, saving, delta = options[-1]
    return (
        None
        if saving <= 0
        else {
            "action": name,
            "expected_kw": saving.quantize(sim.Q2),
            "delta_value": delta,
        }
    )


def _build_steps(connection, scoped, target: Decimal) -> list[dict[str, Any]]:
    """감축 우선순위가 낮은 번호부터 한 대씩, 예상 감축 합이 목표에 닿을 때까지."""
    units = sorted(
        (
            u
            for u in list_master_in(connection, scoped, "hvac_unit")
            if u["isActive"] and u["state"] != "OFF"
        ),
        key=lambda u: (u["curtailPriority"], u["code"]),
    )
    steps: list[dict[str, Any]] = []
    total = Decimal(0)
    for unit in units:
        if total >= target:
            break
        setpoints = _setpoints(connection, scoped, unit["zoneId"])
        temp = _zone_temperature(
            connection, scoped, unit["zoneId"], setpoints["COOL_TEMP"]
        )
        step = _curtail_step(unit, temp, setpoints, target - total)
        if step is None:
            continue
        total += step["expected_kw"]
        steps.append({**step, "seq": len(steps) + 1, "hvac_unit_id": unit["id"]})
    return steps


def _plan(connection, scoped, plan_id: int) -> dict[str, Any] | None:
    plan = _one(connection, PLAN_SQL + " AND id=:id", {**_s(scoped), "id": plan_id})
    if plan is None:
        return None
    plan["steps"] = _all(
        connection,
        "SELECT s.id, s.seq, s.hvac_unit_id, h.code hvac_code, h.name hvac_name, h.curtail_priority, "
        "s.lighting_circuit_id, s.action, s.delta_value, s.expected_kw, s.command_id, s.restore_command_id "
        "FROM bems.demand_plan_step s "
        "LEFT JOIN bems.hvac_unit h ON h.workspace_id=s.workspace_id AND h.generation_id=s.generation_id "
        " AND h.id=s.hvac_unit_id "
        f"WHERE s.{_S.replace(' AND ', ' AND s.')} AND s.demand_plan_id=:p ORDER BY s.seq",
        {**_s(scoped), "p": plan_id},
    )
    return plan


def peak_alarms(context: AuthContext) -> dict[str, Any]:
    """진행 피크 경보와 각 경보의 감축안 여부. FEMS가 꺼져 있으면 알린다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        alarms = _peak_alarms(connection, scoped)
        if alarms is None:
            return {"femsEnabled": False, "rows": []}
        planned = {
            r["femsAlarmRef"]: r["id"]
            for r in _all(connection, PLAN_SQL + " AND status<>'REJECTED'", _s(scoped))
        }
        rows = []
        for a in alarms:
            over = _over_kw(connection, scoped, a)
            rows.append(
                {
                    **a,
                    "alarmRef": _alarm_ref(a),
                    "planId": planned.get(_alarm_ref(a)),
                    "overKw": None if over is None else str(max(Decimal(0), over)),
                }
            )
        return {"femsEnabled": True, "rows": rows}


def demand_plans(context: AuthContext, status: str | None) -> list[dict[str, Any]]:
    where = " AND status=:s" if status else ""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        plans = _all(
            connection,
            PLAN_SQL + where + " ORDER BY proposed_at DESC, id DESC",
            {**_s(scoped), "s": status},
        )
        totals = {
            r["demandPlanId"]: r["expected"]
            for r in _all(
                connection,
                "SELECT demand_plan_id, sum(expected_kw) expected, count(*) steps "
                f"FROM bems.demand_plan_step WHERE {_S} GROUP BY demand_plan_id",
                _s(scoped),
            )
        }
        for plan in plans:
            plan["expectedKw"] = totals.get(plan["id"], "0")
        return plans


def demand_plan(context: AuthContext, plan_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        plan = _plan(connection, scoped, plan_id)
        if plan is None:
            raise _not_found("감축안")
        alarms = _peak_alarms(connection, scoped)
        # 경보가 아직 열려 있으면 복귀는 이르다. FEMS가 꺼져 있으면 판단하지 않는다.
        plan["alarmOpen"] = (
            None
            if alarms is None
            else any(_alarm_ref(a) == plan["femsAlarmRef"] for a in alarms)
        )
        return plan


def propose_plan(context: AuthContext, alarm_ref: str, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        alarms = _peak_alarms(connection, scoped)
        if alarms is None:
            raise _conflict(
                "FEMS를 사용하지 않도록 설정해 피크 경보를 읽을 수 없습니다.",
                "SOURCE_MODULE_DISABLED",
                sourceModule="fems",
            )
        alarm = next((a for a in alarms if _alarm_ref(a) == alarm_ref), None)
        if alarm is None:
            raise _fields({"alarmRef": "진행 중인 피크 경보가 아닙니다."})
        target = _over_kw(connection, scoped, alarm)
        if target is None:
            raise _conflict(
                "계약전력을 알 수 없어 감축할 양을 계산할 수 없습니다. FEMS 요금제를 먼저 등록하세요.",
                "NO_CONTRACT_KW",
            )
        if target <= 0:
            raise _conflict(
                "측정 피크가 한계를 넘지 않아 감축할 양이 없습니다.", "NO_REDUCTION"
            )
        if connection.execute(
            text(
                f"SELECT 1 FROM bems.demand_plan WHERE {_S} AND fems_alarm_ref=:r AND status<>'REJECTED'"
            ),
            {**_s(scoped), "r": alarm_ref},
        ).first():
            raise _conflict("이 경보의 감축안이 이미 있습니다.", "PLAN_EXISTS")
        steps = _build_steps(connection, scoped, target)
        if not steps:
            raise _conflict(
                "운전 중인 공조기가 없어 감축안을 만들 수 없습니다.",
                "NO_CURTAILABLE_UNIT",
            )
        now = _simulation_clock(connection, scoped)[0]
        same_day = connection.execute(
            text(
                f"SELECT count(*) FROM bems.demand_plan WHERE {_S} "
                "AND (proposed_at AT TIME ZONE 'Asia/Seoul')::date=:d"
            ),
            {**_s(scoped), "d": now.astimezone(SEOUL).date()},
        ).scalar_one()
        plan_no = f"PK-{now.astimezone(SEOUL):%Y%m%d}-{same_day + 1:02d}"
        plan_id = connection.execute(
            text(
                "INSERT INTO bems.demand_plan(workspace_id,generation_id,plan_no,fems_alarm_ref,"
                "proposed_at,target_reduction_kw) VALUES (:w,:g,:n,:r,:t,:k) RETURNING id"
            ),
            {**_s(scoped), "n": plan_no, "r": alarm_ref, "t": now, "k": target},
        ).scalar_one()
        for step in steps:
            connection.execute(
                text(
                    "INSERT INTO bems.demand_plan_step(workspace_id,generation_id,demand_plan_id,seq,"
                    "hvac_unit_id,action,delta_value,expected_kw) "
                    "VALUES (:w,:g,:p,:seq,:hvac_unit_id,:action,:delta_value,:expected_kw)"
                ),
                {**_s(scoped), "p": plan_id, **step},
            )
        return _plan(connection, scoped, plan_id), "demand_plan", plan_id

    return _action(context, f"bems.demand_plan.propose:{alarm_ref}", key, {}, fn, 201)


def _decide(connection, scoped, plan_id: int, expected: str, label: str):
    plan = _plan(connection, scoped, plan_id)
    if plan is None:
        raise _not_found("감축안")
    if plan["status"] != expected:
        raise _conflict(
            f"{label} 상태의 감축안만 처리할 수 있습니다.",
            "WRONG_STATUS",
            status=plan["status"],
        )
    return plan


def reject_plan(context: AuthContext, plan_id: int, note: str | None, key: str):
    def fn(connection, scoped):
        _decide(connection, scoped, plan_id, "PROPOSED", "제안")
        connection.execute(
            text(
                f"UPDATE bems.demand_plan SET status='REJECTED', decided_at=clock_timestamp(), "
                f"decision_note=:note WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": plan_id, "note": note},
        )
        return _plan(connection, scoped, plan_id), "demand_plan", plan_id

    return _action(
        context, f"bems.demand_plan.reject:{plan_id}", key, {"note": note}, fn
    )


def approve_plan(context: AuthContext, plan_id: int, note: str | None, key: str):
    """승인과 동시에 단계마다 제어 명령을 낸다(Q2: 자동 제어 없음, 사람이 승인해야 나간다)."""

    def fn(connection, scoped):
        plan = _decide(connection, scoped, plan_id, "PROPOSED", "제안")
        now = _simulation_clock(connection, scoped)[0]
        for step in plan["steps"]:
            unit = _master(connection, scoped, "hvac_unit", step["hvacUnitId"])
            if unit is None:
                continue
            command_id = _execute_step(connection, scoped, plan_id, step, unit, now)
            connection.execute(
                text(
                    f"UPDATE bems.demand_plan_step SET command_id=:c WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "c": command_id, "id": step["id"]},
            )
        connection.execute(
            text(
                f"UPDATE bems.demand_plan SET status='EXECUTED', decided_at=clock_timestamp(), "
                f"executed_at=:t, decision_note=:note WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": plan_id, "t": now, "note": note},
        )
        return _plan(connection, scoped, plan_id), "demand_plan", plan_id

    return _action(
        context, f"bems.demand_plan.approve:{plan_id}", key, {"note": note}, fn
    )


def _execute_step(connection, scoped, plan_id, step, unit, now) -> int:
    row = {
        "zone_id": unit["zoneId"],
        "hvac_unit_id": unit["id"],
        "demand_plan_id": plan_id,
        "source": "PEAK",
        "result": "APPLIED",
        "note": f"피크 감축 {step['seq']}단계",
    }
    if step["action"] == "RAISE_SETPOINT":
        setpoints = _setpoints(connection, scoped, unit["zoneId"])
        value = setpoints["COOL_TEMP"] + Decimal(step["deltaValue"])
        row.update(command="SET_SETPOINT", setpoint_kind="COOL_TEMP", value=value)
        reason = sim.setpoint_error("COOL_TEMP", value, setpoints)
        if reason:
            row.update(result="REJECTED", reject_reason=reason)
        return _insert_command(connection, scoped, row, now)
    if step["action"] == "SET_FAN":
        row.update(command="SET_MODE", mode="FAN")
        command_id = _insert_command(connection, scoped, row, now)
        _set_state(connection, scoped, unit["id"], "FAN", "MANUAL", now)
        return command_id
    row.update(command="POWER_OFF")
    command_id = _insert_command(connection, scoped, row, now)
    _set_state(connection, scoped, unit["id"], "OFF", "MANUAL", now)
    return command_id


def restore_plan(context: AuthContext, plan_id: int, note: str | None, key: str):
    """경보가 해제된 뒤 복귀를 승인하면 공조기를 **스케줄 운전**으로 되돌린다."""

    def fn(connection, scoped):
        plan = _decide(connection, scoped, plan_id, "EXECUTED", "실행")
        alarms = _peak_alarms(connection, scoped)
        if alarms is not None and any(
            _alarm_ref(a) == plan["femsAlarmRef"] for a in alarms
        ):
            raise _conflict(
                "피크 경보가 아직 진행 중입니다. 해제된 뒤에 복귀하세요.", "ALARM_OPEN"
            )
        now = _simulation_clock(connection, scoped)[0]
        for step in plan["steps"]:
            unit = _master(connection, scoped, "hvac_unit", step["hvacUnitId"])
            if unit is None:
                continue
            command_id = _restore_step(connection, scoped, plan_id, step, unit, now)
            connection.execute(
                text(
                    f"UPDATE bems.demand_plan_step SET restore_command_id=:c WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "c": command_id, "id": step["id"]},
            )
        connection.execute(
            text(
                f"UPDATE bems.demand_plan SET status='RESTORED', restored_at=:t WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": plan_id, "t": now},
        )
        return _plan(connection, scoped, plan_id), "demand_plan", plan_id

    return _action(
        context, f"bems.demand_plan.restore:{plan_id}", key, {"note": note}, fn
    )


def _restore_step(connection, scoped, plan_id, step, unit, now) -> int:
    row = {
        "zone_id": unit["zoneId"],
        "hvac_unit_id": unit["id"],
        "demand_plan_id": plan_id,
        "source": "PEAK",
        "result": "APPLIED",
        "note": f"피크 감축 {step['seq']}단계 복귀",
    }
    if step["action"] == "RAISE_SETPOINT":
        setpoints = _setpoints(connection, scoped, unit["zoneId"])
        value = setpoints["COOL_TEMP"] - Decimal(step["deltaValue"])
        row.update(command="SET_SETPOINT", setpoint_kind="COOL_TEMP", value=value)
        reason = sim.setpoint_error("COOL_TEMP", value, setpoints)
        if reason:
            row.update(result="REJECTED", reject_reason=reason)
        return _insert_command(connection, scoped, row, now)
    planned = _scheduled_mode(connection, scoped, unit["id"], now)
    if planned == "OFF":
        row.update(command="POWER_OFF")
        state = "OFF"
    elif unit["state"] == "OFF":
        row.update(command="POWER_ON")
        state = planned
    else:
        row.update(command="SET_MODE", mode=planned)
        state = planned
    command_id = _insert_command(connection, scoped, row, now)
    _set_state(connection, scoped, unit["id"], state, "SCHEDULE", now)
    return command_id


# ---------- 쾌적도 (B-10, DSN-16 F14) ----------
#
# 쾌적 시간 비율 = 쾌적 범위 안 관측 시간 ÷ 센 관측 시간. 저장하지 않고 조회로 계산한다.
# "근무 시간만" 기준은 그 구역의 운전 스케줄(공조기·조명)이 켜져 있도록 잡힌 시각을 쓴다.
# 스케줄이 하나도 없으면 근무 시간을 알 수 없으므로 **0%가 아니라 '모름'**으로 돌려준다.


def _occupied_hours(connection, scoped) -> dict[int, set[tuple[str, int]]]:
    """구역별 (요일 구분, 시각) 집합. 스케줄이 없는 구역은 키 자체가 없다."""
    rows = connection.execute(
        text(
            f"""
        SELECT COALESCE(h.zone_id, l.zone_id) zone_id, s.day_kind, s.start_hour, s.end_hour
        FROM bems.schedule_slot s
        LEFT JOIN bems.hvac_unit h ON h.workspace_id=s.workspace_id AND h.generation_id=s.generation_id AND h.id=s.hvac_unit_id
        LEFT JOIN bems.lighting_circuit l ON l.workspace_id=s.workspace_id AND l.generation_id=s.generation_id AND l.id=s.lighting_circuit_id
        WHERE s.{_S.replace(" AND ", " AND s.")} AND s.is_active
        """
        ),
        _s(scoped),
    ).mappings()
    slots: dict[int, set[tuple[str, int]]] = {}
    for r in rows:
        if r["zone_id"] is None:
            continue
        bucket = slots.setdefault(r["zone_id"], set())
        for hour in range(r["start_hour"], r["end_hour"]):
            bucket.add((r["day_kind"], hour))
    return slots


def comfort(
    context: AuthContext, date_from: date | None, date_to: date | None
) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        start, end = _period(date_from, date_to, 14)
        first, last = start.date(), (end - timedelta(hours=1)).date()
        standards = list_master_in(connection, scoped, "comfort_standard")
        zones = {z["id"]: z for z in list_master_in(connection, scoped, "zone")}
        slots = _occupied_hours(connection, scoped)
        holidays = {h["date"] for h in core.holidays(connection, scoped, first, last)}
        rows = connection.execute(
            text(
                f"""
            SELECT s.zone_id, s.metric, r.period_start, r.value
            FROM bems.environment_reading r
            JOIN bems.sensor s ON s.workspace_id=r.workspace_id AND s.generation_id=r.generation_id AND s.id=r.sensor_id
            WHERE r.{_S.replace(" AND ", " AND r.")} AND r.quality='valid'
              AND r.period_start >= CAST(:start AS timestamptz) AND r.period_start < CAST(:end AS timestamptz)
            """
            ),
            {**_s(scoped), "start": start, "end": end},
        ).mappings()
        counted: dict[tuple[int, str], int] = {}
        inside: dict[tuple[int, str], int] = {}
        by_kind = {(c["zoneKind"], c["metric"]): c for c in standards}
        for r in rows:
            zone = zones.get(r["zone_id"])
            if zone is None:
                continue
            standard = by_kind.get((zone["kind"], r["metric"]))
            if standard is None:
                continue
            local = r["period_start"].astimezone(SEOUL)
            if standard["occupiedOnly"]:
                zone_slots = slots.get(zone["id"])
                if zone_slots is None:
                    continue  # 스케줄이 없는 구역은 아래에서 '모름'으로 답한다.
                kind = (
                    "HOLIDAY"
                    if local.date().isoformat() in holidays
                    else ("WEEKDAY" if local.weekday() < 5 else "WEEKEND")
                )
                if (kind, local.hour) not in zone_slots:
                    continue
            key = (zone["id"], r["metric"])
            counted[key] = counted.get(key, 0) + 1
            low, high = standard["low"], standard["high"]
            value = r["value"]
            if (low is None or value >= Decimal(low)) and (
                high is None or value <= Decimal(high)
            ):
                inside[key] = inside.get(key, 0) + 1
        result = []
        for zone in zones.values():
            for standard in standards:
                if standard["zoneKind"] != zone["kind"]:
                    continue
                key = (zone["id"], standard["metric"])
                hours = counted.get(key, 0)
                unknown = standard["occupiedOnly"] and zone["id"] not in slots
                result.append(
                    {
                        "zoneId": zone["id"],
                        "zoneCode": zone["code"],
                        "zoneName": zone["name"],
                        "zoneKind": zone["kind"],
                        "metric": standard["metric"],
                        "unit": UNITS[standard["metric"]],
                        "low": standard["low"],
                        "high": standard["high"],
                        "occupiedOnly": standard["occupiedOnly"],
                        "hours": hours,
                        "insideHours": inside.get(key, 0),
                        "ratio": None
                        if unknown or not hours
                        else str(
                            (Decimal(inside.get(key, 0)) * 100 / hours).quantize(
                                Decimal("0.1")
                            )
                        ),
                        "reason": "NO_SCHEDULE"
                        if unknown
                        else ("NO_READINGS" if not hours else None),
                    }
                )
        return {"from": first.isoformat(), "to": last.isoformat(), "rows": result}


# ---------- 설비 경보 (B-06, DSN-16 F32) ----------


def _rejected_streak(connection, scoped, unit_id: int, limit: int) -> int:
    """마지막 적용 명령 뒤로 이어진 거부 횟수. 적용이 하나 끼면 거기서 끊긴다."""
    rows = connection.execute(
        text(
            f"SELECT result FROM bems.control_command WHERE {_S} AND hvac_unit_id=:u "
            "ORDER BY requested_at DESC, id DESC LIMIT :n"
        ),
        {**_s(scoped), "u": unit_id, "n": limit},
    ).scalars()
    streak = 0
    for result in rows:
        if result != "REJECTED":
            break
        streak += 1
    return streak


def _running_hours(connection, scoped, unit_id: int, moment: datetime) -> int | None:
    """마지막으로 정지한 뒤 지난 시간. 정지한 적이 없으면 **판단하지 않는다**(None)."""
    stopped = connection.execute(
        text(
            f"SELECT max(requested_at) FROM bems.control_command WHERE {_S} AND hvac_unit_id=:u "
            "AND command='POWER_OFF' AND result='APPLIED' AND requested_at<=:t"
        ),
        {**_s(scoped), "u": unit_id, "t": moment},
    ).scalar()
    if stopped is None:
        return None
    return int((moment - stopped).total_seconds() // 3600)


def _evaluate_equipment_alarms(connection, scoped, moment: datetime) -> tuple[int, int]:
    """규칙·설비당 진행 경보 1건. 조건이 풀리면 그 시각에 해제한다(환경 경보와 같은 수명)."""
    raised = cleared = 0
    rules = [
        r
        for r in list_master_in(connection, scoped, "equipment_alarm_rule")
        if r["isActive"]
    ]
    if not rules:
        return 0, 0
    units = {u["id"]: u for u in list_master_in(connection, scoped, "hvac_unit")}
    for rule in rules:
        threshold = int(Decimal(rule["threshold"]))
        targets = [rule["hvacUnitId"]] if rule["hvacUnitId"] else list(units)
        for unit_id in targets:
            unit = units.get(unit_id)
            if unit is None or not unit["isActive"]:
                continue
            if rule["condition"] == "COMMAND_REJECTED":
                hit = (
                    _rejected_streak(connection, scoped, unit_id, threshold)
                    >= threshold
                )
            else:
                hours = (
                    _running_hours(connection, scoped, unit_id, moment)
                    if unit["state"] != "OFF"
                    else None
                )
                hit = hours is not None and hours >= threshold
            open_alarm = _one(
                connection,
                f"SELECT id FROM bems.equipment_alarm WHERE {_S} AND rule_id=:r "
                "AND hvac_unit_id=:u AND status<>'cleared'",
                {**_s(scoped), "r": rule["id"], "u": unit_id},
            )
            if hit and open_alarm is None:
                connection.execute(
                    text(
                        "INSERT INTO bems.equipment_alarm(workspace_id,generation_id,rule_id,hvac_unit_id,raised_at) "
                        "VALUES (:w,:g,:r,:u,:t) ON CONFLICT DO NOTHING"
                    ),
                    {**_s(scoped), "r": rule["id"], "u": unit_id, "t": moment},
                )
                raised += 1
            elif not hit and open_alarm is not None:
                connection.execute(
                    text(
                        f"UPDATE bems.equipment_alarm SET status='cleared', cleared_at=:t WHERE {_S} AND id=:id"
                    ),
                    {**_s(scoped), "t": moment, "id": open_alarm["id"]},
                )
                cleared += 1
    return raised, cleared


EQUIPMENT_ALARM_SQL = f"""
SELECT a.id, a.rule_id, a.hvac_unit_id, a.status, a.raised_at, a.acknowledged_at, a.cleared_at,
       r.code rule_code, r.condition, r.threshold, r.severity, h.code hvac_code, h.name hvac_name, h.zone_id
FROM bems.equipment_alarm a
JOIN bems.equipment_alarm_rule r ON r.workspace_id=a.workspace_id AND r.generation_id=a.generation_id AND r.id=a.rule_id
JOIN bems.hvac_unit h ON h.workspace_id=a.workspace_id AND h.generation_id=a.generation_id AND h.id=a.hvac_unit_id
WHERE a.{_S.replace(" AND ", " AND a.")}
"""


def equipment_alarms(context: AuthContext, status: str | None) -> list[dict[str, Any]]:
    where = " AND a.status=:s" if status else ""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            EQUIPMENT_ALARM_SQL + where + " ORDER BY a.raised_at DESC, a.id DESC",
            {**_s(scoped), "s": status},
        )


def acknowledge_equipment_alarm(
    context: AuthContext, alarm_id: int, key: str
) -> dict[str, Any]:
    """확인은 사람만 한다. 해제는 1시간 진행의 판정으로만 일어난다(환경 경보와 같다)."""

    def fn(connection, scoped):
        found = _one(
            connection,
            EQUIPMENT_ALARM_SQL + " AND a.id=:id",
            {**_s(scoped), "id": alarm_id},
        )
        if found is None:
            raise _not_found("설비 경보")
        if found["status"] != "raised":
            raise _conflict(
                "확인 대기 상태의 경보만 확인할 수 있습니다.",
                "NOT_RAISED",
                status=found["status"],
            )
        connection.execute(
            text(
                f"UPDATE bems.equipment_alarm SET status='acknowledged', acknowledged_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": alarm_id},
        )
        result = _one(
            connection,
            EQUIPMENT_ALARM_SQL + " AND a.id=:id",
            {**_s(scoped), "id": alarm_id},
        )
        return result, "equipment_alarm", alarm_id

    return _action(context, f"bems.equipment_alarm.ack:{alarm_id}", key, {}, fn)


def advance(context: AuthContext, hours: int, key: str) -> dict[str, Any]:
    def fn(connection, scoped):
        start, limit = _simulation_clock(connection, scoped)
        if start >= limit:
            raise _conflict(
                "업무 기준일 다음 날까지 진행했습니다. 더 진행하려면 세대를 초기화하세요.",
                "SIMULATION_LIMIT",
                limit=limit.isoformat(),
            )
        totals = {"readings": 0, "switches": 0, "raised": 0, "cleared": 0}
        moment = start
        steps = 0
        while steps < hours and moment < limit:
            for k, v in _step(connection, scoped, moment).items():
                totals[k] += v
            moment += timedelta(hours=1)
            steps += 1
        return (
            {
                "from": start.isoformat(),
                "to": moment.isoformat(),
                "hours": steps,
                **totals,
            },
            "simulation",
            0,
        )

    return _action(context, "bems.simulation.advance", key, {"hours": hours}, fn)


def clock(connection, scoped) -> dict[str, Any]:
    start, limit = _simulation_clock(connection, scoped)
    return {
        "next": start.isoformat(),
        "limit": limit.isoformat(),
        "canAdvance": start < limit,
    }


def simulation_clock(context: AuthContext) -> dict[str, Any]:
    with _read() as connection:
        return clock(connection, read_scope(connection, context, MODULE))


# ---------- 경보 (B-06, TX-B3) ----------

ALARM_SQL = f"""
SELECT a.id, a.alarm_rule_id, a.sensor_id, a.status, a.raised_at, a.peak_value, a.acknowledged_at, a.ack_note,
       a.cleared_at, r.zone_id, z.code zone_code, z.name zone_name, r.metric, r.comparator, r.threshold,
       r.duration_hours, r.severity
FROM bems.alarm a
JOIN bems.alarm_rule r ON r.workspace_id=a.workspace_id AND r.generation_id=a.generation_id AND r.id=a.alarm_rule_id
JOIN bems.zone z ON z.workspace_id=r.workspace_id AND z.generation_id=r.generation_id AND z.id=r.zone_id
WHERE a.{_S.replace(" AND ", " AND a.")}
"""


def alarms(context: AuthContext, status: str | None) -> list[dict[str, Any]]:
    where = " AND a.status=:st" if status else ""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            ALARM_SQL + where + " ORDER BY a.raised_at DESC, a.id DESC",
            {**_s(scoped), "st": status},
        )


def acknowledge(
    context: AuthContext, alarm_id: int, note: str | None, key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        found = _one(
            connection, ALARM_SQL + " AND a.id=:id", {**_s(scoped), "id": alarm_id}
        )
        if found is None:
            raise _not_found("경보")
        if found["status"] != "raised":
            raise _conflict(
                "확인 대기 중인 경보만 확인할 수 있습니다.",
                "NOT_RAISED",
                status=found["status"],
            )
        connection.execute(
            text(
                f"UPDATE bems.alarm SET status='acknowledged', acknowledged_at=clock_timestamp(), ack_note=:n "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "n": note, "id": alarm_id},
        )
        return (
            _one(
                connection, ALARM_SQL + " AND a.id=:id", {**_s(scoped), "id": alarm_id}
            ),
            "alarm",
            alarm_id,
        )

    return _action(context, f"bems.alarm.ack:{alarm_id}", key, {"note": note}, fn)


RULE_SQL = f"SELECT id, zone_id, metric, comparator, threshold, duration_hours, severity, is_active FROM bems.alarm_rule WHERE {_S}"


def alarm_rules(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection, RULE_SQL + " ORDER BY zone_id, metric, comparator", _s(scoped)
        )


def create_rule(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        if _master(connection, scoped, "zone", values["zone_id"]) is None:
            raise _fields({"zoneId": "구역을 고르세요."})
        if connection.execute(
            text(
                f"SELECT 1 FROM bems.alarm_rule WHERE {_S} AND zone_id=:zone_id AND metric=:metric AND comparator=:comparator"
            ),
            {**_s(scoped), **values},
        ).first():
            raise _fields({"comparator": "같은 구역·항목·비교의 규칙이 이미 있습니다."})
        row_id = connection.execute(
            text(
                "INSERT INTO bems.alarm_rule(workspace_id,generation_id,zone_id,metric,comparator,threshold,duration_hours,severity) "
                "VALUES (:w,:g,:zone_id,:metric,:comparator,:threshold,:duration_hours,:severity) RETURNING id"
            ),
            {**_s(scoped), **values},
        ).scalar_one()
        return (
            _one(connection, RULE_SQL + " AND id=:id", {**_s(scoped), "id": row_id}),
            "alarm_rule",
            row_id,
        )

    return _action(context, "bems.alarm_rule.create", key, values, fn, 201)


def update_rule(
    context: AuthContext, rule_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def fn(connection, scoped):
        if (
            _one(connection, RULE_SQL + " AND id=:id", {**_s(scoped), "id": rule_id})
            is None
        ):
            raise _not_found("경보 규칙")
        sets = ", ".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE bems.alarm_rule SET {sets} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": rule_id},
        )
        return (
            _one(connection, RULE_SQL + " AND id=:id", {**_s(scoped), "id": rule_id}),
            "alarm_rule",
            rule_id,
        )

    return _action(context, f"bems.alarm_rule.update:{rule_id}", key, values, fn)


# ---------- 대시보드 (B-01) ----------


def dashboard(context: AuthContext) -> dict[str, Any]:
    yesterday = business_today() - timedelta(days=1)
    try:
        week = breakdown(context, "day", yesterday - timedelta(days=6), yesterday)[
            "rows"
        ]
    except ApiError as error:
        if error.details.get("reason") != "SOURCE_MODULE_DISABLED":
            raise
        week = None
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        latest = _latest_environment(connection, scoped)
        zones = []
        units = list_master_in(connection, scoped, "hvac_unit")
        for z in list_master_in(connection, scoped, "zone"):
            zones.append(
                {
                    **z,
                    "environment": latest.get(z["id"], {}),
                    "setpoints": {
                        k: str(v)
                        for k, v in _setpoints(connection, scoped, z["id"]).items()
                    },
                    "hvac": [
                        {
                            "code": u["code"],
                            "state": u["state"],
                            "controlSource": u["controlSource"],
                        }
                        for u in units
                        if u["zoneId"] == z["id"]
                    ],
                }
            )
        open_alarms = _all(
            connection,
            ALARM_SQL + " AND a.status<>'cleared' ORDER BY a.raised_at DESC",
            _s(scoped),
        )
        equipment = _all(
            connection,
            EQUIPMENT_ALARM_SQL + " AND a.status<>'cleared' ORDER BY a.raised_at DESC",
            _s(scoped),
        )
        plans = _all(
            connection,
            PLAN_SQL
            + " AND status IN ('PROPOSED','EXECUTED') ORDER BY proposed_at DESC",
            _s(scoped),
        )
        return {
            "yesterday": yesterday.isoformat(),
            "week": week,
            "zones": zones,
            "alarms": open_alarms,
            "equipmentAlarms": equipment,
            "demandPlans": plans,
            "month": _month_card(context, connection, scoped),
            "clock": clock(connection, scoped),
        }


def _month_card(context: AuthContext, connection, scoped) -> dict[str, Any]:
    """대시보드 이번 달 카드. 원단위·목표 달성률·쾌적 시간 비율은 모르면 None이다."""
    month = business_today().strftime("%Y-%m")
    start, end, first, last = _month_range(month)
    rows = _common_hourly(connection, scoped, start, end)
    total = sum((Decimal(r["kwh"]) for r in rows), Decimal(0))
    area = _gross_area(connection, scoped)
    target = _targets(connection, scoped, month).get(None)
    comfort_rows = comfort(context, first, last)["rows"]
    hours = sum(r["hours"] for r in comfort_rows)
    inside = sum(r["insideHours"] for r in comfort_rows)
    return {
        "month": month,
        "totalKwh": str(total.quantize(MONEY)),
        "euiKwhPerM2": None if not area else str((total / area).quantize(RATIO4)),
        "achievement": _achievement(total, target),
        "comfortRatio": None
        if not hours
        else str((Decimal(inside) / Decimal(hours)).quantize(RATIO4)),
    }
