"""SPC 업무 규칙 (FS-028 모듈 설계 3·5·6장).

- 부분군(D39): MES 공정 실행 1건 안의 한 시각 n=5. MES는 fs.mes.interface로만 읽는다(D9). LOT·공정·설비는 스냅샷.
- 순서(13장 2): 측정 시각은 그 특성의 마지막 유효 부분군보다 늦어야 한다 — 과거 끼워 넣기가 없으니 판정을 다시 계산하지 않는다.
- 관리 한계(D40): 유효 부분군 20개 이상으로 게시, 불변. 적용 시작 = 게시 때 마지막 유효 부분군의 측정 시각
  (벽시계와 무관 — DB·API 시계 차이, 게스트 공간의 날짜 이동에 흔들리지 않는다). 그보다 늦게 측정한 부분군부터 판정한다.
- 이상(D41·D42): 부분군 기록 때 규칙 1~3 판정. 연속 규칙은 같은 버전 안에서만 센다. 발생 → 조치 완료, 부분군 무효 시 무효.
- 공정능력(D43): 저장하지 않고 조회할 때 계산한다.

쓰기는 write_scope의 공간 잠금 뒤에 실행되고, 같은 특성의 기록·게시는 특성 행 잠금으로 직렬화된다(TX-S1·S2·S4).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.mes import interface as mes
from fs.spc import stats

MODULE = "spc"
SEOUL = ZoneInfo("Asia/Seoul")
_S = "workspace_id=:w AND generation_id=:g"
RUN_DAYS = 30  # 측정 입력에 보여 줄 공정 실행 기간(S-04)


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


def _mes_disabled() -> ApiError:
    return _conflict(
        "MES를 사용하지 않도록 설정했습니다. 관리도·공정능력·이상 조치는 그대로 쓸 수 있습니다.",
        "SOURCE_MODULE_DISABLED",
        sourceModule="mes",
    )


Action = Callable[[Connection, AuthContext], tuple[Any, str, int]]


# 공통 엔진(fs.common.engine.action): 공간 잠금 → 멱등 영수증 → 처리 → 영수증 저장
_action = partial(action, MODULE)


def _one(connection, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    row = connection.execute(text(sql), params).mappings().first()
    return None if row is None else _row(row)


def _all(connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [_row(r) for r in connection.execute(text(sql), params).mappings()]


def _number(value: str | None, field: str) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise _fields({field: "숫자를 입력해 주세요."}) from exc


def _now(connection) -> datetime:
    return connection.execute(text("SELECT clock_timestamp()")).scalar_one()


OPEN_END = datetime(9999, 1, 1, tzinfo=SEOUL)


def _period(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    """조회 기간 [from 00:00, to+1 00:00). 시작 기본은 업무 기준일 60일 전(시드 공정 실행 기간).

    종료일이 없으면 끝을 열어 둔다 — 측정 시각은 실제 시각이라 업무 기준일(FS_TODAY)보다 늦을 수 있다.
    """
    last = date_to or business_today()
    first = date_from or last - timedelta(days=60)
    if first > last:
        raise _fields({"from": "시작일은 종료일보다 늦을 수 없습니다."})
    start = datetime.combine(first, time(), SEOUL)
    end = (
        datetime.combine(last + timedelta(days=1), time(), SEOUL)
        if date_to
        else OPEN_END
    )
    return start, end


# ---------- 관리 특성 (S-07) ----------

CHAR_SQL = f"""
SELECT c.id, c.code, c.item_code, c.item_name, c.process_code, c.name, c.unit, c.lsl, c.usl,
       c.target, c.subgroup_size, c.decimals, c.is_active,
       (SELECT count(*) FROM spc.subgroup s WHERE s.workspace_id=c.workspace_id
          AND s.generation_id=c.generation_id AND s.characteristic_id=c.id AND s.status='valid') subgroup_count,
       (SELECT max(l.version) FROM spc.control_limit l WHERE l.workspace_id=c.workspace_id
          AND l.generation_id=c.generation_id AND l.characteristic_id=c.id) limit_version,
       (SELECT count(*) FROM spc.signal x WHERE x.workspace_id=c.workspace_id
          AND x.generation_id=c.generation_id AND x.characteristic_id=c.id AND x.status='open') open_signals
FROM spc.characteristic c WHERE c.{_S.replace(" AND ", " AND c.")}
"""


def _characteristic(connection, scoped, characteristic_id: int) -> dict[str, Any]:
    found = _one(
        connection, CHAR_SQL + " AND c.id=:id", {**_s(scoped), "id": characteristic_id}
    )
    if found is None:
        raise _not_found("관리 특성")
    return found


def characteristics(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(connection, CHAR_SQL + " ORDER BY c.code", _s(scoped))


def characteristic(context: AuthContext, characteristic_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _characteristic(connection, scoped, characteristic_id)


def items(context: AuthContext) -> list[dict[str, Any]]:
    """특성 등록용 MES 완제품 목록(S-07). MES 꺼짐이면 409."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = mes.items(connection, scoped)
        if found is None:
            raise _mes_disabled()
        return found


def _spec(lsl: Decimal | None, usl: Decimal | None, target: Decimal | None) -> None:
    if lsl is None and usl is None:
        raise _fields({"lsl": "규격 하한·상한 중 하나 이상을 입력해 주세요."})
    if lsl is not None and usl is not None and lsl >= usl:
        raise _fields({"usl": "규격 상한은 하한보다 커야 합니다."})
    if target is not None and (
        (lsl is not None and target < lsl) or (usl is not None and target > usl)
    ):
        raise _fields({"target": "목표값은 규격 안이어야 합니다."})


def create_characteristic(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    lsl, usl = _number(values.get("lsl"), "lsl"), _number(values.get("usl"), "usl")
    target = _number(values.get("target"), "target")
    _spec(lsl, usl, target)

    def fn(connection, scoped):
        items = mes.items(connection, scoped)
        if items is None:
            raise _mes_disabled()
        item = next((i for i in items if i["itemCode"] == values["item_code"]), None)
        if item is None:
            raise _fields({"itemCode": "MES 완제품 목록에 있는 품목을 골라 주세요."})
        duplicate = connection.execute(
            text(
                f"SELECT code FROM spc.characteristic WHERE {_S} AND (code=:code "
                "OR (item_code=:item AND process_code=:process AND name=:name))"
            ),
            {
                **_s(scoped),
                "code": values["code"],
                "item": values["item_code"],
                "process": values["process_code"],
                "name": values["name"],
            },
        ).scalar()
        if duplicate is not None:
            raise _conflict(
                "같은 코드나 같은 품목·공정·특성명이 이미 있습니다.",
                "DUPLICATE",
                code=duplicate,
            )
        new_id = connection.execute(
            text(
                "INSERT INTO spc.characteristic(workspace_id,generation_id,code,item_code,item_name,"
                "process_code,name,unit,lsl,usl,target,decimals) VALUES "
                "(:w,:g,:code,:item,:item_name,:process,:name,:unit,:lsl,:usl,:target,:decimals) RETURNING id"
            ),
            {
                **_s(scoped),
                "code": values["code"],
                "item": item["itemCode"],
                "item_name": item["name"],
                "process": values["process_code"],
                "name": values["name"],
                "unit": values["unit"],
                "lsl": lsl,
                "usl": usl,
                "target": target,
                "decimals": values.get("decimals", 3),
            },
        ).scalar_one()
        return _characteristic(connection, scoped, new_id), "characteristic", new_id

    return _action(context, "spc.characteristic.create", key, values, fn, 201)


SPEC_FIELDS = ("unit", "lsl", "usl", "target")


def update_characteristic(
    context: AuthContext, characteristic_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        current = _characteristic(connection, scoped, characteristic_id)
        if int(current["subgroupCount"]) > 0 and any(k in values for k in SPEC_FIELDS):
            raise _conflict(
                "부분군이 있는 특성의 규격·단위는 바꿀 수 없습니다. 새 특성을 등록해 주세요.",
                "CHARACTERISTIC_IN_USE",
                subgroupCount=current["subgroupCount"],
            )
        merged = {
            k: _number(values[k], k) if k in values else _number(current[k], k)
            for k in ("lsl", "usl", "target")
        }
        _spec(merged["lsl"], merged["usl"], merged["target"])
        sets = {
            **values,
            **{k: merged[k] for k in ("lsl", "usl", "target") if k in values},
        }
        if sets:
            assignments = ", ".join(f"{k}=:{k}" for k in sets)
            connection.execute(
                text(
                    f"UPDATE spc.characteristic SET {assignments} WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), **sets, "id": characteristic_id},
            )
        return (
            _characteristic(connection, scoped, characteristic_id),
            "characteristic",
            characteristic_id,
        )

    return _action(
        context, f"spc.characteristic.update:{characteristic_id}", key, values, fn
    )


def _lock(connection, scoped, characteristic_id: int) -> dict[str, Any]:
    found = _one(
        connection,
        f"SELECT id, item_code, process_code, lsl, usl, is_active FROM spc.characteristic "
        f"WHERE {_S} AND id=:id FOR UPDATE",
        {**_s(scoped), "id": characteristic_id},
    )
    if found is None:
        raise _not_found("관리 특성")
    return found


# ---------- 관리 한계 (S-07, TX-S2) ----------

LIMIT_SQL = f"""
SELECT id, characteristic_id, version, effective_at, basis_from, basis_to, basis_count,
       xbar_cl, xbar_ucl, xbar_lcl, r_cl, r_ucl, r_lcl, reason, created_at published_at
FROM spc.control_limit WHERE {_S}
"""


def _limits(connection, scoped, characteristic_id: int) -> list[dict[str, Any]]:
    return _all(
        connection,
        LIMIT_SQL + " AND characteristic_id=:c ORDER BY version",
        {**_s(scoped), "c": characteristic_id},
    )


def limits(context: AuthContext, characteristic_id: int) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        _characteristic(connection, scoped, characteristic_id)
        return _limits(connection, scoped, characteristic_id)


def _basis(
    connection, scoped, characteristic_id: int, basis_from: datetime, basis_to: datetime
) -> dict[str, Any]:
    if basis_from > basis_to:
        raise _fields({"basisTo": "기준 구간 종료는 시작보다 늦어야 합니다."})
    rows = connection.execute(
        text(
            f"SELECT xbar, r FROM spc.subgroup WHERE {_S} AND characteristic_id=:c "
            "AND status='valid' AND measured_at BETWEEN :a AND :b ORDER BY measured_at"
        ),
        {**_s(scoped), "c": characteristic_id, "a": basis_from, "b": basis_to},
    ).all()
    result: dict[str, Any] = {"basisCount": len(rows), "minimum": stats.MIN_BASIS}
    if len(rows) >= stats.MIN_BASIS:
        computed = stats.limits([r.xbar for r in rows], [r.r for r in rows])
        result.update({_camel(k): v for k, v in computed.items()})
    return result


def preview_limit(
    context: AuthContext,
    characteristic_id: int,
    basis_from: datetime,
    basis_to: datetime,
) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        _characteristic(connection, scoped, characteristic_id)
        found = _basis(connection, scoped, characteristic_id, basis_from, basis_to)
        return {k: _value(v) for k, v in found.items()}


def publish_limit(
    context: AuthContext, characteristic_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        _lock(connection, scoped, characteristic_id)
        found = _basis(
            connection,
            scoped,
            characteristic_id,
            values["basis_from"],
            values["basis_to"],
        )
        if found["basisCount"] < stats.MIN_BASIS:
            raise _fields(
                {
                    "basisFrom": f"유효 부분군이 {stats.MIN_BASIS}개 이상이어야 합니다(현재 {found['basisCount']}개)."
                }
            )
        last = connection.execute(
            text(
                f"SELECT max(measured_at) FROM spc.subgroup WHERE {_S} AND characteristic_id=:c AND status='valid'"
            ),
            {**_s(scoped), "c": characteristic_id},
        ).scalar_one()
        previous = connection.execute(
            text(
                f"SELECT max(effective_at) FROM spc.control_limit WHERE {_S} AND characteristic_id=:c"
            ),
            {**_s(scoped), "c": characteristic_id},
        ).scalar()
        if previous is not None and last <= previous:
            raise _conflict(
                "직전 한계 게시 뒤 새 부분군이 없습니다. 부분군을 더 기록한 뒤 게시해 주세요.",
                "NO_NEW_SUBGROUP",
            )
        if found["rCl"] <= 0:
            raise _fields(
                {
                    "basisFrom": "기준 구간의 범위(R)가 모두 0이라 한계를 만들 수 없습니다."
                }
            )
        version = connection.execute(
            text(
                f"SELECT COALESCE(max(version),0)+1 FROM spc.control_limit WHERE {_S} AND characteristic_id=:c"
            ),
            {**_s(scoped), "c": characteristic_id},
        ).scalar_one()
        new_id = connection.execute(
            text(
                "INSERT INTO spc.control_limit(workspace_id,generation_id,characteristic_id,version,"
                "effective_at,basis_from,basis_to,basis_count,xbar_cl,xbar_ucl,xbar_lcl,r_cl,r_ucl,r_lcl,reason) "
                "VALUES (:w,:g,:c,:v,:at,:a,:b,:n,:xc,:xu,:xl,:rc,:ru,:rl,:reason) RETURNING id"
            ),
            {
                **_s(scoped),
                "c": characteristic_id,
                "v": version,
                "at": last,
                "a": values["basis_from"],
                "b": values["basis_to"],
                "n": found["basisCount"],
                "xc": found["xbarCl"],
                "xu": found["xbarUcl"],
                "xl": found["xbarLcl"],
                "rc": found["rCl"],
                "ru": found["rUcl"],
                "rl": found["rLcl"],
                "reason": values["reason"],
            },
        ).scalar_one()
        return (
            _one(connection, LIMIT_SQL + " AND id=:id", {**_s(scoped), "id": new_id}),
            "control_limit",
            new_id,
        )

    return _action(
        context,
        f"spc.limit.publish:{characteristic_id}",
        key,
        {
            **values,
            "basis_from": values["basis_from"].isoformat(),
            "basis_to": values["basis_to"].isoformat(),
        },
        fn,
        201,
    )


# ---------- 측정 입력 (S-04, TX-S1) ----------


def runs(context: AuthContext, characteristic_id: int) -> list[dict[str, Any]]:
    """MES 공정 실행(해당 품목·공정, 최근 30일) + 실행별 기록된 부분군 수."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _characteristic(connection, scoped, characteristic_id)
        today = business_today()
        rows = mes.operation_runs(
            connection,
            scoped,
            today - timedelta(days=RUN_DAYS),
            today + timedelta(days=1),
        )
        if rows is None:
            raise _mes_disabled()
        counts = dict(
            connection.execute(
                text(
                    f"SELECT lot_no, count(*) FROM spc.subgroup WHERE {_S} AND characteristic_id=:c "
                    "AND status='valid' GROUP BY lot_no"
                ),
                {**_s(scoped), "c": characteristic_id},
            ).all()
        )
        return [
            {**r, "subgroupCount": counts.get(r["lotNo"], 0)}
            for r in rows
            if r["itemCode"] == found["itemCode"]
            and r["processCode"] == found["processCode"]
        ]


def _judging_limit(connection, scoped, characteristic_id: int, measured_at: datetime):
    return (
        connection.execute(
            text(
                LIMIT_SQL
                + " AND characteristic_id=:c AND effective_at<:t ORDER BY effective_at DESC LIMIT 1"
            ),
            {**_s(scoped), "c": characteristic_id, "t": measured_at},
        )
        .mappings()
        .first()
    )


def record_subgroup(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    numbers = []
    for index, raw in enumerate(values["values"], 1):
        try:
            number = Decimal(raw)
        except InvalidOperation as exc:
            raise _fields({f"values.{index}": "숫자를 입력해 주세요."}) from exc
        if (
            not number.is_finite()
            or abs(number) >= Decimal("1e8")
            or number.as_tuple().exponent < -4
        ):
            raise _fields(
                {f"values.{index}": "소수 4자리 이하의 숫자를 입력해 주세요."}
            )
        numbers.append(number)
    measured_at: datetime = values["measured_at"]
    if measured_at.tzinfo is None:
        raise _fields({"measuredAt": "시간대가 포함된 시각이어야 합니다."})

    def fn(connection, scoped):
        found = _lock(connection, scoped, values["characteristic_id"])
        if not found["isActive"]:
            raise _conflict("사용하지 않는 관리 특성입니다.", "CHARACTERISTIC_INACTIVE")
        today = business_today()
        rows = mes.operation_runs(
            connection,
            scoped,
            today - timedelta(days=RUN_DAYS),
            today + timedelta(days=1),
        )
        if rows is None:
            raise _mes_disabled()
        run = next(
            (
                r
                for r in rows
                if r["lotNo"] == values["lot_no"]
                and r["itemCode"] == found["itemCode"]
                and r["processCode"] == found["processCode"]
            ),
            None,
        )
        if run is None:
            raise _fields(
                {"lotNo": "이 특성의 품목·공정으로 시작된 MES 공정 실행이 아닙니다."}
            )
        started = datetime.fromisoformat(run["startedAt"])
        ended = datetime.fromisoformat(run["endedAt"]) if run["endedAt"] else None
        upper = ended or _now(connection)
        if not (started <= measured_at <= upper):
            raise _fields({"measuredAt": "공정 실행 기간(시작~종료) 안이어야 합니다."})
        last = connection.execute(
            text(
                f"SELECT max(measured_at) FROM spc.subgroup WHERE {_S} AND characteristic_id=:c AND status='valid'"
            ),
            {**_s(scoped), "c": values["characteristic_id"]},
        ).scalar()
        if last is not None and measured_at <= last:
            raise _fields(
                {
                    "measuredAt": f"이 특성의 마지막 부분군({last.astimezone(SEOUL):%m-%d %H:%M})보다 늦어야 합니다."
                }
            )
        xbar, r = stats.subgroup(numbers)
        subgroup_id = connection.execute(
            text(
                "INSERT INTO spc.subgroup(workspace_id,generation_id,characteristic_id,lot_no,item_code,"
                "process_code,equipment_code,run_started_at,run_ended_at,measured_at,xbar,r,source,note) "
                "VALUES (:w,:g,:c,:lot,:item,:process,:equipment,:started,:ended,:at,:xbar,:r,'MANUAL',:note) RETURNING id"
            ),
            {
                **_s(scoped),
                "c": values["characteristic_id"],
                "lot": run["lotNo"],
                "item": run["itemCode"],
                "process": run["processCode"],
                "equipment": run["equipmentCode"],
                "started": started,
                "ended": ended,
                "at": measured_at,
                "xbar": xbar,
                "r": r,
                "note": values.get("note"),
            },
        ).scalar_one()
        for seq, number in enumerate(numbers, 1):
            connection.execute(
                text(
                    "INSERT INTO spc.measurement(workspace_id,generation_id,subgroup_id,seq,value) "
                    "VALUES (:w,:g,:sg,:seq,:v)"
                ),
                {**_s(scoped), "sg": subgroup_id, "seq": seq, "v": number},
            )
        created = _evaluate(
            connection,
            scoped,
            values["characteristic_id"],
            subgroup_id,
            run["lotNo"],
            measured_at,
            xbar,
            r,
        )
        return (
            {**_subgroup(connection, scoped, subgroup_id), "signals": created},
            "subgroup",
            subgroup_id,
        )

    body = {**values, "measured_at": measured_at.isoformat()}
    return _action(context, "spc.subgroup.create", key, body, fn, 201)


def _evaluate(
    connection, scoped, characteristic_id, subgroup_id, lot_no, measured_at, xbar, r
):
    limit = _judging_limit(connection, scoped, characteristic_id, measured_at)
    if limit is None:
        return []  # 한계 게시 전 부분군은 판정하지 않는다(AC-172)
    previous = [
        row.xbar
        for row in connection.execute(
            text(
                f"SELECT xbar FROM spc.subgroup WHERE {_S} AND characteristic_id=:c AND status='valid' "
                "AND measured_at>:start AND measured_at<:at AND id<>:id ORDER BY measured_at"
            ),
            {
                **_s(scoped),
                "c": characteristic_id,
                "start": limit["effective_at"],
                "at": measured_at,
                "id": subgroup_id,
            },
        )
    ]
    created = []
    for chart, rule, value in stats.signals(previous, xbar, r, limit):
        connection.execute(
            text(
                "INSERT INTO spc.signal(workspace_id,generation_id,subgroup_id,characteristic_id,"
                "control_limit_id,lot_no,chart,rule,value,detected_at) "
                "VALUES (:w,:g,:sg,:c,:l,:lot,:chart,:rule,:v,:at)"
            ),
            {
                **_s(scoped),
                "sg": subgroup_id,
                "c": characteristic_id,
                "l": limit["id"],
                "lot": lot_no,
                "chart": chart,
                "rule": rule,
                "v": value,
                "at": measured_at,
            },
        )
        created.append({"chart": chart, "rule": rule, "value": str(value)})
    return created


SUBGROUP_SQL = f"""
SELECT s.id, s.characteristic_id, s.lot_no, s.item_code, s.process_code, s.equipment_code,
       s.run_started_at, s.run_ended_at, s.measured_at, s.xbar, s.r, s.status, s.void_reason,
       s.voided_at, s.source, s.note,
       ARRAY(SELECT m.value::text FROM spc.measurement m WHERE m.workspace_id=s.workspace_id
             AND m.generation_id=s.generation_id AND m.subgroup_id=s.id ORDER BY m.seq) measurements
FROM spc.subgroup s WHERE s.{_S.replace(" AND ", " AND s.")}
"""


def _subgroup(connection, scoped, subgroup_id: int) -> dict[str, Any]:
    found = _one(
        connection, SUBGROUP_SQL + " AND s.id=:id", {**_s(scoped), "id": subgroup_id}
    )
    if found is None:
        raise _not_found("부분군")
    return found


def subgroups(
    context: AuthContext,
    characteristic_id: int | None,
    lot_no: str | None,
    status: str | None,
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            SUBGROUP_SQL + " AND (CAST(:c AS bigint) IS NULL OR s.characteristic_id=:c)"
            " AND (CAST(:lot AS text) IS NULL OR s.lot_no=:lot)"
            " AND (CAST(:st AS text) IS NULL OR s.status=:st) ORDER BY s.measured_at DESC LIMIT 500",
            {**_s(scoped), "c": characteristic_id, "lot": lot_no, "st": status},
        )


def void_subgroup(
    context: AuthContext, subgroup_id: int, reason: str, key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        found = _subgroup(connection, scoped, subgroup_id)
        _lock(connection, scoped, found["characteristicId"])
        if found["status"] != "valid":
            raise _conflict("유효한 부분군만 무효로 할 수 있습니다.", "NOT_VALID")
        connection.execute(
            text(
                f"UPDATE spc.subgroup SET status='void', void_reason=:reason, voided_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "reason": reason, "id": subgroup_id},
        )
        # 이 부분군에서 나온 이상은 조치 완료된 것도 무효(D42). 뒤 부분군 판정은 다시 계산하지 않는다(13장 4).
        voided = connection.execute(
            text(
                f"UPDATE spc.signal SET status='void', voided_at=clock_timestamp() "
                f"WHERE {_S} AND subgroup_id=:id AND status<>'void'"
            ),
            {**_s(scoped), "id": subgroup_id},
        ).rowcount
        return (
            {**_subgroup(connection, scoped, subgroup_id), "voidedSignals": voided},
            "subgroup",
            subgroup_id,
        )

    return _action(
        context, f"spc.subgroup.void:{subgroup_id}", key, {"reason": reason}, fn
    )


# ---------- 관리도 (S-02) · 공정능력 (S-03) ----------


def chart(
    context: AuthContext,
    characteristic_id: int,
    date_from: date | None,
    date_to: date | None,
) -> dict[str, Any]:
    start, end = _period(date_from, date_to)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _characteristic(connection, scoped, characteristic_id)
        limits_ = _limits(connection, scoped, characteristic_id)
        points = _all(
            connection,
            f"SELECT id, lot_no, equipment_code, measured_at, xbar, r, status FROM spc.subgroup "
            f"WHERE {_S} AND characteristic_id=:c AND measured_at>=:a AND measured_at<:b ORDER BY measured_at",
            {**_s(scoped), "c": characteristic_id, "a": start, "b": end},
        )
        marks: dict[int, list[dict[str, Any]]] = {}
        for sig in _all(
            connection,
            f"SELECT id, subgroup_id, chart, rule, status FROM spc.signal WHERE {_S} "
            "AND characteristic_id=:c AND detected_at>=:a AND detected_at<:b",
            {**_s(scoped), "c": characteristic_id, "a": start, "b": end},
        ):
            marks.setdefault(sig["subgroupId"], []).append(sig)
        starts = [datetime.fromisoformat(v["effectiveAt"]) for v in limits_]
        for p in points:
            at = datetime.fromisoformat(p["measuredAt"])
            applicable = [v for v, s in zip(limits_, starts, strict=True) if s < at]
            p["limitVersion"] = applicable[-1]["version"] if applicable else None
            p["signals"] = marks.get(p["id"], [])
        return {"characteristic": found, "limits": limits_, "points": points}


def capability(
    context: AuthContext,
    characteristic_id: int,
    date_from: date | None,
    date_to: date | None,
) -> dict[str, Any]:
    start, end = _period(date_from, date_to)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _characteristic(connection, scoped, characteristic_id)
        params = {**_s(scoped), "c": characteristic_id, "a": start, "b": end}
        rows = connection.execute(
            text(
                f"SELECT id, xbar, r FROM spc.subgroup WHERE {_S} AND characteristic_id=:c "
                "AND status='valid' AND measured_at>=:a AND measured_at<:b"
            ),
            params,
        ).all()
        open_signals = connection.execute(
            text(
                f"SELECT count(*) FROM spc.signal WHERE {_S} AND characteristic_id=:c AND status='open' "
                "AND detected_at>=:a AND detected_at<:b"
            ),
            params,
        ).scalar_one()
        result: dict[str, Any] = {
            "characteristic": found,
            "subgroupCount": len(rows),
            "minimum": stats.MIN_BASIS,
            "openSignals": open_signals,
            "insufficient": len(rows) < stats.MIN_BASIS,
        }
        if result["insufficient"]:
            return result
        values = list(
            connection.execute(
                text(
                    "SELECT m.value FROM spc.measurement m JOIN spc.subgroup s ON s.workspace_id=m.workspace_id "
                    "AND s.generation_id=m.generation_id AND s.id=m.subgroup_id "
                    "WHERE m.workspace_id=:w AND m.generation_id=:g AND s.characteristic_id=:c "
                    "AND s.status='valid' AND s.measured_at>=:a AND s.measured_at<:b"
                ),
                params,
            ).scalars()
        )
        lsl, usl = _number(found["lsl"], "lsl"), _number(found["usl"], "usl")
        computed = stats.capability(
            [r.xbar for r in rows], [r.r for r in rows], lsl, usl
        )
        result.update({k: _value(v) for k, v in computed.items()})
        result["histogram"] = [
            {k: _value(v) for k, v in b.items()} for b in stats.histogram(values)
        ]
        return result


# ---------- 이상·조치 (S-05, TX-S3) ----------

SIGNAL_SQL = f"""
SELECT x.id, x.subgroup_id, x.characteristic_id, c.code characteristic_code, c.item_code,
       c.process_code, c.name characteristic_name, x.lot_no, s.equipment_code, x.chart, x.rule,
       x.value, x.detected_at, x.status, x.cause_category, x.action, x.resolved_at, x.voided_at,
       l.version limit_version
FROM spc.signal x
JOIN spc.characteristic c ON c.workspace_id=x.workspace_id AND c.generation_id=x.generation_id AND c.id=x.characteristic_id
JOIN spc.subgroup s ON s.workspace_id=x.workspace_id AND s.generation_id=x.generation_id AND s.id=x.subgroup_id
JOIN spc.control_limit l ON l.workspace_id=x.workspace_id AND l.generation_id=x.generation_id AND l.id=x.control_limit_id
WHERE x.{_S.replace(" AND ", " AND x.")}
"""


def signals(
    context: AuthContext, status: str | None, characteristic_id: int | None
) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return _all(
            connection,
            SIGNAL_SQL + " AND (CAST(:st AS text) IS NULL OR x.status=:st)"
            " AND (CAST(:c AS bigint) IS NULL OR x.characteristic_id=:c)"
            " ORDER BY x.detected_at DESC, x.id DESC",
            {**_s(scoped), "st": status, "c": characteristic_id},
        )


def resolve_signal(
    context: AuthContext, signal_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    def fn(connection, scoped):
        found = _one(
            connection,
            SIGNAL_SQL + " AND x.id=:id FOR UPDATE OF x",
            {**_s(scoped), "id": signal_id},
        )
        if found is None:
            raise _not_found("이상 기록")
        if found["status"] != "open":
            raise _conflict(
                "미조치 이상만 조치할 수 있습니다.", "NOT_OPEN", status=found["status"]
            )
        connection.execute(
            text(
                "UPDATE spc.signal SET status='resolved', cause_category=:cause, action=:action, "
                f"resolved_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {
                **_s(scoped),
                "cause": values["cause_category"],
                "action": values["action"].strip(),
                "id": signal_id,
            },
        )
        return (
            _one(
                connection,
                SIGNAL_SQL + " AND x.id=:id",
                {**_s(scoped), "id": signal_id},
            ),
            "signal",
            signal_id,
        )

    return _action(context, f"spc.signal.resolve:{signal_id}", key, values, fn)


# ---------- 대시보드 (S-01) ----------


def dashboard(context: AuthContext) -> dict[str, Any]:
    today = business_today()
    week_start = datetime.combine(today - timedelta(days=6), time(), SEOUL)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        cards = []
        for ch in _all(
            connection, CHAR_SQL + " AND c.is_active ORDER BY c.code", _s(scoped)
        ):
            recent = _all(
                connection,
                f"SELECT measured_at, xbar FROM (SELECT measured_at, xbar FROM spc.subgroup WHERE {_S} "
                "AND characteristic_id=:c AND status='valid' ORDER BY measured_at DESC LIMIT 20) t ORDER BY measured_at",
                {**_s(scoped), "c": ch["id"]},
            )
            limit = _one(
                connection,
                LIMIT_SQL + " AND characteristic_id=:c ORDER BY version DESC LIMIT 1",
                {**_s(scoped), "c": ch["id"]},
            )
            rows = connection.execute(
                text(
                    f"SELECT xbar, r FROM spc.subgroup WHERE {_S} AND characteristic_id=:c AND status='valid'"
                ),
                {**_s(scoped), "c": ch["id"]},
            ).all()
            cap = None
            if len(rows) >= stats.MIN_BASIS:
                computed = stats.capability(
                    [r.xbar for r in rows],
                    [r.r for r in rows],
                    _number(ch["lsl"], "lsl"),
                    _number(ch["usl"], "usl"),
                )
                cap = {
                    "cpk": _value(computed["cpk"]),
                    "judgement": computed["judgement"],
                }
            cards.append({**ch, "recent": recent, "limit": limit, "capability": cap})
        week = connection.execute(
            text(
                f"SELECT count(*) FROM spc.subgroup WHERE {_S} AND status='valid' AND measured_at>=:a"
            ),
            {**_s(scoped), "a": week_start},
        ).scalar_one()
        judgements = [c["capability"]["judgement"] for c in cards if c["capability"]]
        cards.sort(
            key=lambda c: (
                -int(c["openSignals"]),
                Decimal(c["capability"]["cpk"])
                if c["capability"] and c["capability"]["cpk"]
                else Decimal(99),
            )
        )
        return {
            "characteristicCount": len(cards),
            "openSignals": sum(int(c["openSignals"]) for c in cards),
            "openSignalCharacteristics": sum(
                1 for c in cards if int(c["openSignals"]) > 0
            ),
            "capability": {
                j: judgements.count(j) for j in ("CAPABLE", "MARGINAL", "INCAPABLE")
            },
            "weekSubgroups": week,
            "cards": cards,
        }
