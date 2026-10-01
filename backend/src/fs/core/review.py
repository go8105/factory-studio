"""FS-040 런처 평가: 솔루션별 별점·한줄평. 공간을 넘는 집계는 이 테이블만 한다(D73)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import Field
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.core.schema import ApiModel
from fs.core.service import guest_nickname

MODULES = ("mes", "erp", "fems", "qms", "wms", "bems", "spc")
OPERATION = "review.create"

router = APIRouter()


class ReviewCreate(ApiModel):
    module_key: str = Field(alias="moduleKey")
    rating: int = Field(ge=1, le=5)
    comment: str = Field(max_length=200)
    nickname: str | None = Field(None, max_length=100)


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(400, "VALIDATION_FAILED", message, {"fields": {field: message}})


def _module(value: str) -> str:
    if value not in MODULES:
        raise _invalid("moduleKey", "평가할 수 없는 솔루션입니다.")
    return value


def _actor(context: AuthContext) -> dict[str, Any]:
    guest = context.actor_key if context.actor_kind == "GUEST" else None
    return {"user": context.user_id, "guest": guest}


_MINE = "(user_id=CAST(:user AS bigint) OR guest_actor_key=CAST(:guest AS uuid))"


def summary(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"""
            SELECT module_key, round(avg(rating),1) average, count(*) total,
                   coalesce(bool_or({_MINE}), false) reviewed
            FROM core.app_review GROUP BY module_key ORDER BY module_key
            """
        ),
        _actor(context),
    ).mappings()
    return [
        {
            "moduleKey": r["module_key"],
            "average": float(r["average"]),
            "count": r["total"],
            "reviewed": r["reviewed"],
        }
        for r in rows
    ]


def recent(connection: Connection, module_key: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            """
            SELECT nickname, rating, comment, created_at FROM core.app_review
            WHERE module_key=:m ORDER BY created_at DESC, id DESC LIMIT 5
            """
        ),
        {"m": _module(module_key)},
    ).mappings()
    return [
        {
            "nickname": r["nickname"],
            "rating": r["rating"],
            "comment": r["comment"],
            "createdAt": r["created_at"].isoformat(),
        }
        for r in rows
    ]


def create(
    connection: Connection, context: AuthContext, payload: ReviewCreate, key: str
) -> dict[str, Any]:
    module_key = _module(payload.module_key)
    comment = payload.comment.strip()
    if not 2 <= len(comment) <= 100:
        raise _invalid("comment", "한줄평을 2~100자로 입력하세요.")
    if context.actor_kind == "GUEST":
        nickname = guest_nickname(payload.nickname)
    else:
        nickname = connection.execute(
            text("SELECT left(display_name,20) FROM core.app_user WHERE id=:u"),
            {"u": context.user_id},
        ).scalar_one()
    digest = request_digest(
        {
            "moduleKey": module_key,
            "rating": payload.rating,
            "comment": comment,
            "nickname": nickname,
        }
    )
    cached = find_receipt(connection, context, OPERATION, key, digest)
    if cached is not None:
        return cached
    params = {**_actor(context), "m": module_key}
    if connection.execute(
        text(f"SELECT 1 FROM core.app_review WHERE module_key=:m AND {_MINE}"), params
    ).first():
        raise ApiError(409, "ALREADY_REVIEWED", "이미 평가한 솔루션입니다.")
    if (
        context.actor_kind == "GUEST"
        and connection.execute(
            text(
                "SELECT 1 FROM core.app_review WHERE module_key=:m AND actor_kind='GUEST' AND nickname=:n"
            ),
            {"m": module_key, "n": nickname},
        ).first()
    ):
        raise _conflict_nickname()
    try:
        with connection.begin_nested():
            row = (
                connection.execute(
                    text(
                        """
                    INSERT INTO core.app_review
                      (module_key,actor_kind,user_id,guest_actor_key,nickname,rating,comment)
                    VALUES (:m,:kind,:user,CAST(:guest AS uuid),:n,:rating,:comment)
                    RETURNING id, created_at
                        """
                    ),
                    {
                        "m": module_key,
                        "kind": context.actor_kind,
                        **_actor(context),
                        "n": nickname,
                        "rating": payload.rating,
                        "comment": comment,
                    },
                )
                .mappings()
                .one()
            )
    except IntegrityError as exc:
        # 동시 요청이 앞 검사를 함께 통과한 경우. 어느 유니크인지는 인덱스 이름으로 가른다.
        if "c864_uidx" in str(exc.orig):
            raise _conflict_nickname() from exc
        raise ApiError(409, "ALREADY_REVIEWED", "이미 평가한 솔루션입니다.") from exc
    data = {
        "id": row["id"],
        "moduleKey": module_key,
        "nickname": nickname,
        "rating": payload.rating,
        "comment": comment,
        "createdAt": row["created_at"].isoformat(),
    }
    save_receipt(
        connection, context, OPERATION, key, digest, "app_review", row["id"], data, 201
    )
    return data


def _conflict_nickname() -> ApiError:
    return ApiError(
        409,
        "NICKNAME_TAKEN",
        "이 별칭으로 이미 평가가 있습니다. 다른 별칭을 쓰세요.",
        {"fields": {"nickname": "이 별칭으로 이미 평가가 있습니다."}},
    )


@router.get("/reviews/summary")
def get_summary(
    context: Annotated[AuthContext, Depends(resolve_auth)],
) -> dict[str, object]:
    with get_engine().connect() as connection:
        return {"data": summary(connection, context)}


@router.get("/reviews")
def get_reviews(
    context: Annotated[AuthContext, Depends(resolve_auth)],
    module_key: Annotated[str, Query(alias="moduleKey")] = "",
) -> dict[str, object]:
    with get_engine().connect() as connection:
        return {"data": recent(connection, module_key)}


@router.post("/reviews", status_code=201)
def post_review(
    payload: ReviewCreate,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> dict[str, object]:
    require_csrf(context, x_csrf_token)
    if not idempotency_key or len(idempotency_key) > 100:
        raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key가 필요합니다.")
    with get_engine().begin() as connection:
        return {"data": create(connection, context, payload, idempotency_key)}
