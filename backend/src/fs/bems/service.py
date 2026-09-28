"""BEMS 업무 규칙 (FS-025 모듈 설계 3·5·6장).

- 공용 계측·환경 관측은 1시간 구간, 불변. 과거는 시드, 이후는 "1시간 진행"(TX-B2)이 만든다.
- 분해(D20): 잔여 = FEMS 사업장 전력 − FEMS 제조 전력 − BEMS 공용 전력. FEMS는 fs.fems.interface로만 읽는다(D9).
  잔여가 음수면 숨기지 않고 불일치로 표시한다. 저장하지 않는다.
- 공조(D21): 모의 공조기 상태는 제어 명령(TX-B1)과 스케줄 경계 전환으로만 바뀐다. 설정값은 명령 이력의 마지막 적용값이다.
- 경보(D22): 규칙 조건이 지속 시간 동안 참이면 발생, 1시간 거짓이면 해제, 확인은 사람만(TX-B3).

쓰기는 write_scope의 공간 잠금 뒤에 실행되므로 진행·명령이 공간 안에서 직렬화된다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from fs.bems import simulation as sim
from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import read_scope, write_scope
from fs.fems import interface as fems

MODULE = "bems"
SEOUL = ZoneInfo("Asia/Seoul")
_S = "workspace_id=:w AND generation_id=:g"
UNITS = {"TEMP": "℃", "HUMIDITY": "%", "CO2": "ppm"}


# ---------- 공통 ----------


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _read():
    engine = get_engine().execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    return engine.begin()


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


def _action(
    context: AuthContext,
    operation: str,
    key: str,
    body: Any,
    fn: Action,
    status: int = 200,
) -> Any:
    """쓰기 한 건: 공간 잠금 → 멱등 영수증 확인 → 처리 → 영수증 저장(같은 트랜잭션)."""
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        digest = request_digest(body)
        cached = find_receipt(connection, scoped, operation, key, digest)
        if cached is not None:
            return cached
        result, entity, entity_id = fn(connection, scoped)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            entity,
            entity_id,
            result,
            status,
        )
        return result


def _one(connection, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    row = connection.execute(text(sql), params).mappings().first()
    return None if row is None else _row(row)


def _all(connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [_row(r) for r in connection.execute(text(sql), params).mappings()]


# ---------- 기준정보 (B-07) ----------

MASTER = {
    "zone": ("구역", "code, name, kind, floor_area_m2, is_active"),
    "meter": ("공용 계측기", "zone_id, code, name, usage, unit, is_active"),
    "sensor": ("환경 센서", "zone_id, code, metric, unit, is_active"),
    "hvac_unit": (
        "공조기",
        "zone_id, code, name, meter_id, rated_kw, state, control_source, state_changed_at, is_active",
    ),
}


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
    columns = MASTER[table][1]
    where = " AND zone_id=:z" if zone_id and table != "zone" else ""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            f"SELECT id, {columns} FROM bems.{table} WHERE {_S}{where} ORDER BY code",
            {**_s(scoped), "z": zone_id},
        )


def _check_refs(connection, scoped, table: str, values: dict[str, Any]) -> None:
    errors: dict[str, str] = {}
    if (
        "zone_id" in values
        and _master(connection, scoped, "zone", values["zone_id"]) is None
    ):
        errors["zoneId"] = "구역을 고르세요."
    if table == "hvac_unit" and values.get("meter_id") is not None:
        meter = _master(connection, scoped, "meter", values["meter_id"])
        zone = values.get("zone_id")
        if (
            meter is None
            or meter["usage"] != "HVAC"
            or (zone and meter["zoneId"] != zone)
        ):
            errors["meterId"] = "같은 구역의 공조 용도 계측기만 고를 수 있습니다."
    if errors:
        raise _fields(errors)


def create_master(
    context: AuthContext, table: str, values: dict[str, Any], key: str
) -> dict[str, Any]:

    def fn(connection, scoped):
        if connection.execute(
            text(f"SELECT 1 FROM bems.{table} WHERE {_S} AND code=:c"),
            {**_s(scoped), "c": values["code"]},
        ).first():
            raise _fields({"code": "이미 사용 중인 코드입니다."})
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
        if table == "hvac_unit" and "meter_id" in values:
            _check_refs(
                connection, scoped, table, {**values, "zone_id": found["zoneId"]}
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


def _scheduled_mode(connection, scoped, unit_id: int, moment: datetime) -> str:
    local = moment.astimezone(SEOUL)
    kind = "WEEKDAY" if local.weekday() < 5 else "WEEKEND"
    mode = connection.execute(
        text(
            f"SELECT mode FROM bems.schedule_slot WHERE {_S} AND hvac_unit_id=:u AND is_active "
            "AND day_kind=:k AND start_hour<=:h AND end_hour>:h ORDER BY start_hour LIMIT 1"
        ),
        {**_s(scoped), "u": unit_id, "k": kind, "h": local.hour},
    ).scalar()
    return mode or "OFF"


COMMAND_SQL = f"""
SELECT c.id, c.zone_id, c.hvac_unit_id, h.code hvac_code, c.command, c.mode, c.setpoint_kind, c.value, c.source,
       c.requested_at, c.result, c.reject_reason, c.note
FROM bems.control_command c
LEFT JOIN bems.hvac_unit h ON h.workspace_id=c.workspace_id AND h.generation_id=c.generation_id AND h.id=c.hvac_unit_id
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
        f"SELECT id, {MASTER[table][1]} FROM bems.{table} WHERE {_S} ORDER BY code",
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
            + " AND (c.hvac_unit_id=:u OR (c.hvac_unit_id IS NULL AND c.zone_id=:z)) "
            "ORDER BY c.requested_at DESC, c.id DESC LIMIT 20",
            {**_s(scoped), "u": unit_id, "z": unit["zoneId"]},
        )
        unit["schedule"] = _schedule(connection, scoped, unit_id)
        return unit


def commands(
    context: AuthContext, zone_id: int | None, unit_id: int | None
) -> list[dict[str, Any]]:
    where = ""
    if zone_id:
        where += " AND c.zone_id=:z"
    if unit_id:
        where += " AND c.hvac_unit_id=:u"
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            COMMAND_SQL + where + " ORDER BY c.requested_at DESC, c.id DESC LIMIT 200",
            {**_s(scoped), "z": zone_id, "u": unit_id},
        )


def _insert_command(
    connection, scoped, values: dict[str, Any], at: datetime | None = None
) -> int:
    return connection.execute(
        text(
            "INSERT INTO bems.control_command(workspace_id,generation_id,zone_id,hvac_unit_id,command,mode,"
            "setpoint_kind,value,source,requested_at,result,reject_reason,note) VALUES "
            "(:w,:g,:zone_id,:hvac_unit_id,:command,:mode,:setpoint_kind,:value,:source,"
            "COALESCE(CAST(:at AS timestamptz), clock_timestamp()),:result,:reject_reason,:note) RETURNING id"
        ),
        {
            **_s(scoped),
            "hvac_unit_id": None,
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
) -> None:
    connection.execute(
        text(
            f"UPDATE bems.hvac_unit SET state=:s, control_source=:src, "
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
        if command == "SET_SETPOINT":
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


def _schedule(connection, scoped, unit_id: int) -> list[dict[str, Any]]:
    return _all(
        connection,
        f"SELECT id, day_kind, start_hour, end_hour, mode, is_active FROM bems.schedule_slot "
        f"WHERE {_S} AND hvac_unit_id=:u ORDER BY day_kind DESC, start_hour",
        {**_s(scoped), "u": unit_id},
    )


def replace_schedule(
    context: AuthContext, unit_id: int, slots: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    errors: dict[str, str] = {}
    for i, a in enumerate(slots):
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
        if _master(connection, scoped, "hvac_unit", unit_id) is None:
            raise _not_found("공조기")
        connection.execute(
            text(f"DELETE FROM bems.schedule_slot WHERE {_S} AND hvac_unit_id=:u"),
            {**_s(scoped), "u": unit_id},
        )
        for slot in slots:
            connection.execute(
                text(
                    "INSERT INTO bems.schedule_slot(workspace_id,generation_id,hvac_unit_id,day_kind,start_hour,end_hour,mode) "
                    "VALUES (:w,:g,:u,:day_kind,:start_hour,:end_hour,:mode)"
                ),
                {**_s(scoped), "u": unit_id, **slot},
            )
        return _schedule(connection, scoped, unit_id), "hvac_unit", unit_id

    return _action(context, f"bems.schedule:{unit_id}", key, {"slots": slots}, fn)


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
    weekday = local.weekday() < 5
    summary = {"readings": 0, "switches": 0, "raised": 0, "cleared": 0}
    units = list_master_in(connection, scoped, "hvac_unit")
    previous = moment - timedelta(hours=1)
    for u in units:
        if not u["isActive"]:
            continue
        planned = _scheduled_mode(connection, scoped, u["id"], moment)
        boundary = planned != _scheduled_mode(connection, scoped, u["id"], previous)
        if (u["controlSource"] == "SCHEDULE" or boundary) and (
            u["state"] != planned or u["controlSource"] != "SCHEDULE"
        ):
            command = (
                "POWER_OFF"
                if planned == "OFF"
                else ("POWER_ON" if u["state"] == "OFF" else "SET_MODE")
            )
            _insert_command(
                connection,
                scoped,
                {
                    "zone_id": u["zoneId"],
                    "hvac_unit_id": u["id"],
                    "command": command,
                    "mode": planned if command == "SET_MODE" else None,
                    "source": "SCHEDULE",
                    "result": "APPLIED",
                },
                moment,
            )
            _set_state(connection, scoped, u["id"], planned, "SCHEDULE", moment)
            u["state"], u["controlSource"] = planned, "SCHEDULE"
            summary["switches"] += 1
    latest = _latest_environment(connection, scoped)
    zones = list_master_in(connection, scoped, "zone")
    state_by_zone = {u["zoneId"]: u["state"] for u in units if u["isActive"]}
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
        if "CO2" in values:
            nxt["CO2"] = sim.next_co2(
                Decimal(values["CO2"]),
                local.hour,
                weekday,
                z["kind"] == "OFFICE",
                state,
            )
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
    raised, cleared = _evaluate_alarms(connection, scoped, moment)
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
        return {
            "yesterday": yesterday.isoformat(),
            "week": week,
            "zones": zones,
            "alarms": open_alarms,
            "clock": clock(connection, scoped),
        }
