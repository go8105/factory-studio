# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""공통 휴일 달력 API (DSN-16 Q1, P-08). 휴일은 core 소유이고 업무 솔루션은 날짜로만 읽는다.

공간·세대마다 자기 달력을 가진다. 회원 공간(회사)은 ADMIN만 고치고, 체험 공간은 본인이 고친다.
"""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from fs.common.auth import AuthContext, resolve_auth
from fs.common.clock import business_today
from fs.common.engine import action, mutation_key, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]
_S = "workspace_id=:w AND generation_id=:g"
Kind = Literal["PUBLIC", "COMPANY"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class HolidayCreate(ApiModel):
    holiday_on: date = Field(alias="date")
    name: str = Field(min_length=1, max_length=60)
    kind: Kind = "COMPANY"


class HolidayUpdate(ApiModel):
    holiday_on: date | None = Field(None, alias="date")
    name: str | None = Field(None, min_length=1, max_length=60)
    kind: Kind | None = None


def _wire(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "date": row["holiday_on"].isoformat(),
        "name": row["name"],
        "kind": row["kind"],
    }


def _fields(fields: dict[str, str]) -> ApiError:
    return ApiError(
        400, "VALIDATION_FAILED", "입력값을 확인해 주세요.", {"fields": fields}
    )


def _authorize(_connection, context: AuthContext) -> None:
    if context.actor_kind == "MEMBER" and "ADMIN" not in context.roles:
        raise ApiError(403, "FORBIDDEN", "휴일 달력은 관리자만 고칠 수 있습니다.")


def _reject_taken(connection, params, day: date, exclude: int | None = None) -> None:
    if connection.execute(
        text(
            f"SELECT 1 FROM core.holiday WHERE {_S} AND holiday_on=:d AND id IS DISTINCT FROM :id"
        ),
        {**params, "d": day, "id": exclude},
    ).first():
        raise _fields({"date": "이 날짜에는 이미 휴일이 있습니다."})


def _find(connection, scoped: AuthContext, holiday_id: int):
    row = (
        connection.execute(
            text(
                f"SELECT id, holiday_on, name, kind FROM core.holiday WHERE {_S} AND id=:id"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "id": holiday_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "휴일을 찾을 수 없습니다.")
    return row


@router.get("")
def list_holidays(
    context: Auth, year: Annotated[int | None, Query(ge=2000, le=2100)] = None
):
    year = year or business_today().year
    with read() as connection:
        scoped = read_scope(connection, context, "core")
        rows = connection.execute(
            text(
                f"SELECT id, holiday_on, name, kind FROM core.holiday WHERE {_S} "
                "AND holiday_on BETWEEN :first AND :last ORDER BY holiday_on"
            ),
            {
                "w": scoped.workspace_id,
                "g": scoped.generation_id,
                "first": date(year, 1, 1),
                "last": date(year, 12, 31),
            },
        ).mappings()
        wired = [_wire(r) for r in rows]
        # 한 해 휴일은 수십 건이라 쪽수를 나누지 않는다. 목록 화면의 "총 N건"을 위해 수만 알린다.
        return {
            "data": wired,
            "page": {"offset": 0, "limit": len(wired) or 1, "total": len(wired)},
        }


@router.post("", status_code=201)
def create_holiday(
    payload: HolidayCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    key = mutation_key(context, csrf, key)
    if not 2000 <= payload.holiday_on.year <= 2100:
        raise _fields({"date": "2000~2100년 사이 날짜를 고르세요."})
    name = payload.name.strip()
    if not name:
        raise _fields({"name": "이름을 입력하세요."})

    def fn(connection, scoped):
        params = {"w": scoped.workspace_id, "g": scoped.generation_id}
        _reject_taken(connection, params, payload.holiday_on)
        row = (
            connection.execute(
                text(
                    "INSERT INTO core.holiday(workspace_id,generation_id,holiday_on,name,kind) "
                    "VALUES (:w,:g,:d,:n,:k) RETURNING id, holiday_on, name, kind"
                ),
                {**params, "d": payload.holiday_on, "n": name, "k": payload.kind},
            )
            .mappings()
            .one()
        )
        return {"data": _wire(row)}, "holiday", row["id"]

    return action(
        "core",
        context,
        "core.holiday.create",
        key,
        payload.model_dump(mode="json", by_alias=True),
        fn,
        201,
        authorize=_authorize,
    )


@router.patch("/{holiday_id}")
def update_holiday(
    holiday_id: int,
    payload: HolidayUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    key = mutation_key(context, csrf, key)
    values = payload.model_dump(exclude_unset=True)
    if not values or any(v is None for v in values.values()):
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목을 입력하세요.")
    if "name" in values:
        values["name"] = values["name"].strip()
        if not values["name"]:
            raise _fields({"name": "이름을 입력하세요."})
    if "holiday_on" in values and not 2000 <= values["holiday_on"].year <= 2100:
        raise _fields({"date": "2000~2100년 사이 날짜를 고르세요."})

    def fn(connection, scoped):
        _find(connection, scoped, holiday_id)
        params = {"w": scoped.workspace_id, "g": scoped.generation_id}
        if "holiday_on" in values:
            _reject_taken(connection, params, values["holiday_on"], holiday_id)
        sets = ", ".join(f"{k}=:{k}" for k in values)
        row = (
            connection.execute(
                text(
                    f"UPDATE core.holiday SET {sets} WHERE {_S} AND id=:id "
                    "RETURNING id, holiday_on, name, kind"
                ),
                {
                    "w": scoped.workspace_id,
                    "g": scoped.generation_id,
                    "id": holiday_id,
                    **values,
                },
            )
            .mappings()
            .one()
        )
        return {"data": _wire(row)}, "holiday", holiday_id

    return action(
        "core",
        context,
        f"core.holiday.update:{holiday_id}",
        key,
        {k: v.isoformat() if isinstance(v, date) else v for k, v in values.items()},
        fn,
        authorize=_authorize,
    )


@router.delete("/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    key = mutation_key(context, csrf, key)

    def fn(connection, scoped):
        row = _find(connection, scoped, holiday_id)
        connection.execute(
            text(f"DELETE FROM core.holiday WHERE {_S} AND id=:id"),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "id": holiday_id},
        )
        return {"data": _wire(row)}, "holiday", holiday_id

    return action(
        "core",
        context,
        f"core.holiday.delete:{holiday_id}",
        key,
        {},
        fn,
        authorize=_authorize,
    )
