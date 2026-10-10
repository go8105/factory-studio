"""회사 실제 근무: 버튼 원장·분 단위 신청·권한/멱등/마감. 개인 AUTO 근태와 분리."""

import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.core.company import companies, resolve_company

S = "workspace_id=:w AND generation_id=:g"


def now():
    return datetime.now(UTC)


def invalid(message):
    raise ApiError(400, "VALIDATION_FAILED", message)


def scope(ctx):
    return {"w": ctx.workspace_id, "g": ctx.generation_id}


def principal(c, ctx, admin=False):
    # 재확인: 계정/소속 회수는 새 조회와 영수증 재전송에도 적용한다.
    resolve_company(c, ctx, ctx.workspace_id)
    row = (
        c.execute(
            text(f"""SELECT a.employee_id AS id,a.work_role AS role,e.name,e.employee_code AS code
      FROM hr.work_account a JOIN hr.employee e
      ON (e.workspace_id,e.generation_id,e.id)=(a.workspace_id,a.generation_id,a.employee_id)
      WHERE a.{S.replace(" AND ", " AND a.")} AND a.user_id=:u AND a.is_active AND e.status='ACTIVE' """),
            {**scope(ctx), "u": ctx.user_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None or (admin and row["role"] != "ADMIN"):
        raise ApiError(
            403, "WORK_ACCESS_DENIED", "사원 연결 또는 근태 관리 권한이 필요합니다."
        )
    return dict(row)


def policy(c, ctx):
    return dict(
        c.execute(text(f"SELECT * FROM hr.work_policy WHERE {S}"), scope(ctx))
        .mappings()
        .one()
    )


def event(c, ctx, employee, action_name, entity, summary):
    c.execute(
        text("""INSERT INTO hr.work_event(workspace_id,generation_id,employee_id,actor_user_id,action,entity_id,summary)
      VALUES (:w,:g,:e,:u,:a,:id,CAST(:s AS jsonb))"""),
        {
            **scope(ctx),
            "e": employee,
            "u": ctx.user_id,
            "a": action_name,
            "id": entity,
            "s": json.dumps(jsonable_encoder(summary), ensure_ascii=False),
        },
    )


def open_month(c, ctx, days):
    for month in {d.strftime("%Y-%m") for d in days}:
        if c.execute(
            text(f"SELECT 1 FROM hr.work_close WHERE {S} AND month=:m"),
            {**scope(ctx), "m": month},
        ).first():
            raise ApiError(
                409, "MONTH_CLOSED", "마감한 월의 근무 기록은 변경할 수 없습니다."
            )


def days_between(start, end):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def granted(c, ctx, employee, year):
    days = c.execute(
        text(
            f"SELECT granted_days FROM hr.leave_balance WHERE {S} AND employee_id=:e AND leave_year=:year"
        ),
        {**scope(ctx), "e": employee, "year": str(year)},
    ).scalar_one_or_none()
    return int((days or 0) * policy(c, ctx)["daily_minutes"])


def deduction(c, ctx, person, year):
    return c.execute(
        text(f"""SELECT coalesce(sum(minutes),0) FROM hr.work_request WHERE {S}
      AND employee_id=:e AND status IN ('APPROVED','CANCEL_REQUESTED') AND kind <> 'TRIP'
      AND extract(year FROM starts_at AT TIME ZONE 'Asia/Seoul')=:year"""),
        {**scope(ctx), "e": person, "year": year},
    ).scalar_one()


def company_list(ctx):
    with read() as c:
        return companies(c, ctx)


def overview(ctx, company_id, month):
    with read() as c:
        ctx, company = resolve_company(c, ctx, company_id)
        ctx = read_scope(c, ctx, "hr")
        person = principal(c, ctx)
        p = policy(c, ctx)
        year = int(month[:4])
        begin = date.fromisoformat(month + "-01")
        end = (begin.replace(day=28) + timedelta(days=4)).replace(day=1)
        employee_filter = "" if person["role"] == "ADMIN" else " AND employee_id=:e"
        params = {**scope(ctx), "e": person["id"], "begin": begin, "end": end}
        sessions = [
            dict(r)
            for r in c.execute(
                text(f"""SELECT x.*,e.name AS "employeeName" FROM hr.clock_session x JOIN hr.employee e
          ON (x.workspace_id,x.generation_id,x.employee_id)=(e.workspace_id,e.generation_id,e.id)
          WHERE x.{S.replace(" AND ", " AND x.")} AND work_date>=:begin AND work_date<:end
          {employee_filter} ORDER BY work_date DESC,x.id DESC"""),
                params,
            ).mappings()
        ]
        requests = [
            dict(r)
            for r in c.execute(
                text(f"""SELECT x.*,e.name AS "employeeName" FROM hr.work_request x JOIN hr.employee e
          ON (x.workspace_id,x.generation_id,x.employee_id)=(e.workspace_id,e.generation_id,e.id)
          WHERE x.{S.replace(" AND ", " AND x.")} {employee_filter} ORDER BY x.id DESC LIMIT 200"""),
                params,
            ).mappings()
        ]
        active = (
            c.execute(
                text(
                    f"SELECT * FROM hr.clock_session WHERE {S} AND employee_id=:e AND clock_out IS NULL"
                ),
                params,
            )
            .mappings()
            .first()
        )
        records = [
            dict(r)
            for r in c.execute(
                text(
                    f"""SELECT * FROM hr.work_event WHERE {S} {employee_filter} ORDER BY id DESC LIMIT 100"""
                ),
                params,
            ).mappings()
        ]
        return jsonable_encoder(
            {
                "company": company,
                "person": person,
                "policy": p,
                "month": month,
                "remainingMinutes": granted(c, ctx, person["id"], year)
                - deduction(c, ctx, person["id"], year),
                "activeSession": dict(active) if active else None,
                "sessions": sessions,
                "requests": requests,
                "events": records,
                "closed": bool(
                    c.execute(
                        text(f"SELECT 1 FROM hr.work_close WHERE {S} AND month=:m"),
                        {**params, "m": month},
                    ).first()
                ),
            }
        )


def mutate(ctx, company_id, operation, key, body):
    with read() as c:
        company_ctx, company = resolve_company(c, ctx, company_id)
    admin = operation in {"approve", "reject", "correct", "close"}

    def authorize(c, sc):
        principal(c, sc, admin)

    def run(c, sc):
        person = principal(c, sc, admin)
        p = policy(c, sc)
        params = {**scope(sc), "e": person["id"]}
        timestamp = now()
        tz = ZoneInfo(company["timezone"])
        today = timestamp.astimezone(tz).date()
        if operation in {"clock-in", "clock-out"}:
            opened = (
                c.execute(
                    text(
                        f"SELECT * FROM hr.clock_session WHERE {S} AND employee_id=:e AND clock_out IS NULL FOR UPDATE"
                    ),
                    params,
                )
                .mappings()
                .first()
            )
            if operation == "clock-in":
                open_month(c, sc, [today])
                if (
                    opened
                    or c.execute(
                        text(
                            f"SELECT 1 FROM hr.clock_session WHERE {S} AND employee_id=:e AND work_date=:day"
                        ),
                        {**params, "day": today},
                    ).first()
                ):
                    raise ApiError(
                        409, "ALREADY_CLOCKED_IN", "이미 출근 기록이 있습니다."
                    )
                entity = c.execute(
                    text("""INSERT INTO hr.clock_session(workspace_id,generation_id,employee_id,work_date,clock_in)
                  VALUES (:w,:g,:e,:day,:time) RETURNING id"""),
                    {**params, "day": today, "time": timestamp},
                ).scalar_one()
            else:
                if opened is None:
                    raise ApiError(
                        409, "NOT_CLOCKED_IN", "퇴근할 출근 기록이 없습니다."
                    )
                open_month(c, sc, [opened["work_date"], today])
                entity = opened["id"]
                if timestamp < opened["clock_in"]:
                    invalid("서버 시각이 출근 시각보다 이전입니다.")
                c.execute(
                    text(
                        f"UPDATE hr.clock_session SET clock_out=:time WHERE {S} AND id=:id"
                    ),
                    {**params, "id": entity, "time": timestamp},
                )
            result = {"id": entity, "recordedAt": timestamp.isoformat()}
            event(c, sc, person["id"], operation, entity, result)
        elif operation == "request":
            kind = body["kind"]
            start = datetime.fromisoformat(body["startsAt"])
            end = datetime.fromisoformat(body["endsAt"])
            if start.tzinfo is None or end.tzinfo is None:
                invalid("시간대가 포함된 시각이 필요합니다.")
            start = start.astimezone(tz)
            end = end.astimezone(tz)
            if start >= end or (end - start).days > 31 or start.year != end.year:
                invalid("동일 연도 안의 최대 31일 기간을 선택하세요.")
            if start.second or end.second or start.microsecond or end.microsecond:
                invalid("분 단위 시각을 선택하세요.")
            all_days = list(days_between(start.date(), end.date()))
            open_month(c, sc, all_days)
            minutes = 0
            for day in all_days:
                if (
                    day.weekday() >= 5
                    or c.execute(
                        text(
                            f"SELECT 1 FROM core.holiday WHERE {S} AND holiday_on=:day"
                        ),
                        {**params, "day": day},
                    ).first()
                ):
                    continue
                periods = [
                    (p["start_time"], p["break_start"]),
                    (p["break_end"], p["end_time"]),
                ]
                for a, b in periods:
                    left = max(start, datetime.combine(day, a, tz))
                    right = min(end, datetime.combine(day, b, tz))
                    minutes += max(0, int((right - left).total_seconds() / 60))
            if kind == "TRIP":
                if not body.get("destination"):
                    invalid("출장 행선지를 입력하세요.")
                minutes = 0
            else:
                if minutes <= 0:
                    invalid("근무시간에 해당하는 기간을 선택하세요.")
                if kind == "HOURLY":
                    if start.date() != end.date() or minutes % 60:
                        invalid("시간차는 같은 날 1시간 단위로 신청하세요.")
                    if start.time() < p["start_time"] or end.time() > p["end_time"]:
                        invalid("시간차는 근무시간 안에서 선택하세요.")
                if kind in {"HALF_AM", "HALF_PM"} and (
                    start.date() != end.date() or minutes * 2 != p["daily_minutes"]
                ):
                    invalid("반차는 하루 근무시간의 절반으로 신청하세요.")
                if kind == "HALF_AM" and start.time() != p["start_time"]:
                    invalid("오전 반차는 근무 시작부터 신청하세요.")
                if kind == "HALF_PM" and end.time() != p["end_time"]:
                    invalid("오후 반차는 근무 종료까지 신청하세요.")
                if kind == "ANNUAL" and (
                    start.time() != p["start_time"] or end.time() != p["end_time"]
                ):
                    invalid("연차는 하루 근무 전체 기간으로 신청하세요.")
                if deduction(c, sc, person["id"], start.year) + minutes > granted(
                    c, sc, person["id"], start.year
                ):
                    invalid("연차 잔여 시간이 부족합니다.")
            if c.execute(
                text(f"""SELECT 1 FROM hr.work_request WHERE {S} AND employee_id=:e AND status IN ('REQUESTED','APPROVED','CANCEL_REQUESTED')
               AND starts_at<:end AND ends_at>:start"""),
                {**params, "start": start, "end": end},
            ).first():
                invalid("이미 신청한 기간과 겹칩니다.")
            entity = c.execute(
                text("""INSERT INTO hr.work_request(workspace_id,generation_id,employee_id,kind,starts_at,ends_at,minutes,reason,destination)
                VALUES (:w,:g,:e,:kind,:start,:end,:minutes,:reason,:destination) RETURNING id"""),
                {
                    **params,
                    "kind": kind,
                    "start": start,
                    "end": end,
                    "minutes": minutes,
                    "reason": body["reason"],
                    "destination": body.get("destination"),
                },
            ).scalar_one()
            result = {"id": entity, "minutes": minutes, "status": "REQUESTED"}
            event(c, sc, person["id"], operation, entity, result)
        elif operation in {"approve", "reject", "cancel"}:
            row = (
                c.execute(
                    text(
                        f"SELECT * FROM hr.work_request WHERE {S} AND id=:id FOR UPDATE"
                    ),
                    {**params, "id": body["id"]},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ApiError(404, "NOT_FOUND", "신청을 찾을 수 없습니다.")
            open_month(
                c,
                sc,
                days_between(
                    row["starts_at"].astimezone(tz).date(),
                    row["ends_at"].astimezone(tz).date(),
                ),
            )
            if operation == "cancel":
                if row["employee_id"] != person["id"] or row["status"] not in {
                    "REQUESTED",
                    "APPROVED",
                }:
                    raise ApiError(
                        409,
                        "PRECONDITION_NOT_MET",
                        "본인의 신청 또는 승인된 건만 취소 요청할 수 있습니다.",
                    )
                status = (
                    "CANCELLED" if row["status"] == "REQUESTED" else "CANCEL_REQUESTED"
                )
            else:
                if row["employee_id"] == person["id"]:
                    raise ApiError(
                        403,
                        "SELF_APPROVAL_DENIED",
                        "자기 신청은 승인하거나 반려할 수 없습니다.",
                    )
                if row["status"] not in {"REQUESTED", "CANCEL_REQUESTED"}:
                    raise ApiError(
                        409, "PRECONDITION_NOT_MET", "이미 처리된 신청입니다."
                    )
                if row["status"] == "CANCEL_REQUESTED":
                    status = "CANCELLED" if operation == "approve" else "APPROVED"
                else:
                    if (
                        operation == "approve"
                        and row["kind"] != "TRIP"
                        and deduction(
                            c,
                            sc,
                            row["employee_id"],
                            row["starts_at"].astimezone(tz).year,
                        )
                        + row["minutes"]
                        > granted(
                            c,
                            sc,
                            row["employee_id"],
                            row["starts_at"].astimezone(tz).year,
                        )
                    ):
                        invalid("승인할 연차 잔여 시간이 부족합니다.")
                    status = "APPROVED" if operation == "approve" else "REJECTED"
            c.execute(
                text(
                    f"UPDATE hr.work_request SET status=:status,decided_by=:actor,decided_at=:at WHERE {S} AND id=:id"
                ),
                {
                    **params,
                    "id": row["id"],
                    "status": status,
                    "actor": person["id"],
                    "at": timestamp,
                },
            )
            entity = row["id"]
            result = {"id": entity, "status": status}
            event(
                c,
                sc,
                row["employee_id"],
                operation,
                entity,
                {"before": row["status"], "after": status},
            )
        elif operation == "correct":
            row = (
                c.execute(
                    text(
                        f"SELECT * FROM hr.clock_session WHERE {S} AND id=:id FOR UPDATE"
                    ),
                    {**params, "id": body["id"]},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ApiError(404, "NOT_FOUND", "출퇴근 기록을 찾을 수 없습니다.")
            start = datetime.fromisoformat(body["clockIn"])
            end = (
                datetime.fromisoformat(body["clockOut"])
                if body.get("clockOut")
                else None
            )
            if (
                start.tzinfo is None
                or (end and end.tzinfo is None)
                or (end and end < start)
                or start > timestamp
                or (end and end > timestamp)
            ):
                invalid("정정 시각 또는 시간대를 확인하세요.")
            if start.astimezone(tz).date() != row["work_date"]:
                invalid("출근 근무일은 변경할 수 없습니다.")
            open_month(
                c,
                sc,
                [
                    row["work_date"],
                    end.astimezone(tz).date() if end else row["work_date"],
                ],
            )
            if row["clock_out"]:
                open_month(c, sc, [row["clock_out"].astimezone(tz).date()])
            if (
                end is None
                and c.execute(
                    text(
                        f"SELECT 1 FROM hr.clock_session WHERE {S} AND employee_id=:employee AND clock_out IS NULL AND id<>:id"
                    ),
                    {**params, "employee": row["employee_id"], "id": row["id"]},
                ).first()
            ):
                invalid("다른 열린 출근 기록이 있어 퇴근 시각을 비울 수 없습니다.")
            c.execute(
                text(
                    f"UPDATE hr.clock_session SET clock_in=:start,clock_out=:end WHERE {S} AND id=:id"
                ),
                {**params, "id": row["id"], "start": start, "end": end},
            )
            entity = row["id"]
            result = {"id": entity}
            event(
                c,
                sc,
                row["employee_id"],
                operation,
                entity,
                {"before": dict(row), "after": body},
            )
        elif operation == "close":
            month = body["month"]
            begin = date.fromisoformat(month + "-01")
            end = (begin.replace(day=28) + timedelta(days=4)).replace(day=1)
            if end > today:
                invalid("종료된 월만 마감할 수 있습니다.")
            open_month(c, sc, [begin])
            if c.execute(
                text(f"""SELECT 1 FROM hr.clock_session WHERE {S} AND work_date>=:begin AND work_date<:end AND clock_out IS NULL
               UNION ALL SELECT 1 FROM hr.work_request WHERE {S} AND status IN ('REQUESTED','CANCEL_REQUESTED') AND starts_at<:end_at AND ends_at>=:begin_at"""),
                {
                    **params,
                    "begin": begin,
                    "end": end,
                    "begin_at": datetime.combine(begin, datetime.min.time(), tz),
                    "end_at": datetime.combine(end, datetime.min.time(), tz),
                },
            ).first():
                invalid("퇴근 누락 또는 미처리 신청을 먼저 처리하세요.")
            entity = c.execute(
                text(
                    """INSERT INTO hr.work_close(workspace_id,generation_id,month,closed_by) VALUES (:w,:g,:m,:e) RETURNING id"""
                ),
                {**params, "m": month},
            ).scalar_one()
            result = {"id": entity, "month": month}
            event(c, sc, person["id"], operation, entity, result)
        else:
            invalid("지원하지 않는 동작입니다.")
        return jsonable_encoder(result), "hr.work", entity

    return action(
        "hr", company_ctx, "hr.work." + operation, key, body, run, authorize=authorize
    )
