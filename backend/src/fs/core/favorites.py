"""Workspace-owned menu preferences; no business data or cross-module writes."""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import ConfigDict, Field, model_validator
from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.core.schema import ApiModel
from fs.core.service import _audit, _workspace_lock


@lru_cache
def catalog() -> dict:
    return json.loads(files("fs.core").joinpath("menu_catalog.json").read_text())


class MenuPreferencesUpdate(ApiModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    menu_ids: list[str] = Field(alias="menuIds", max_length=200)
    sidebar_mode: Literal["all", "favorites"] = Field(alias="sidebarMode")
    expected_version: int = Field(alias="expectedVersion", ge=1)

    @model_validator(mode="after")
    def valid_menus(self):
        valid = {
            f"{solution['key']}:{screen['path']}"
            for solution in catalog()["solutions"]
            for screen in solution["screens"]
        }
        if len(self.menu_ids) != len(set(self.menu_ids)):
            raise ValueError("같은 메뉴를 두 번 등록할 수 없습니다.")
        if not set(self.menu_ids) <= valid:
            raise ValueError("현재 제공되는 메뉴만 등록할 수 있습니다.")
        return self


def _row(connection: Connection, context: AuthContext):
    # Settings are independent of a data generation; a reset preserves them.
    row = (
        connection.execute(
            text("""SELECT menu_preferences,menu_preferences_version FROM core.workspace
        WHERE id=:w AND active_generation_id=:g AND workspace_kind IN ('MEMBER','GUEST')"""),
            {"w": context.workspace_id, "g": context.generation_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "공간을 찾을 수 없습니다.")
    return row


def _wire(row):
    preferences = row["menu_preferences"]
    if preferences is None:
        preferences = {
            "menuIds": catalog()["defaultMenuIds"],
            "sidebarMode": "favorites",
        }
    return {**preferences, "version": row["menu_preferences_version"]}


def read(connection: Connection, context: AuthContext):
    return _wire(_row(connection, context))


def update(
    connection: Connection,
    context: AuthContext,
    payload: MenuPreferencesUpdate,
    key: str,
):
    _workspace_lock(connection, context.workspace_id)
    row = _row(connection, context)
    body = payload.model_dump(by_alias=True)
    digest = request_digest(body)
    cached = find_receipt(connection, context, "workspace.menus.update", key, digest)
    if cached is not None:
        return cached
    if row["menu_preferences_version"] != payload.expected_version:
        raise ApiError(
            409,
            "VERSION_CONFLICT",
            "다른 창에서 메뉴 구성이 변경되었습니다. 최신 구성을 불러오세요.",
        )
    preferences = {"menuIds": payload.menu_ids, "sidebarMode": payload.sidebar_mode}
    result = (
        connection.execute(
            text("""UPDATE core.workspace SET menu_preferences=CAST(:preferences AS jsonb),
        menu_preferences_version=menu_preferences_version+1 WHERE id=:w
        RETURNING menu_preferences,menu_preferences_version"""),
            {"w": context.workspace_id, "preferences": json.dumps(preferences)},
        )
        .mappings()
        .one()
    )
    response = _wire(result)
    save_receipt(
        connection,
        context,
        "workspace.menus.update",
        key,
        digest,
        "workspace",
        context.workspace_id,
        response,
    )
    _audit(
        connection,
        context.workspace_id,
        context.actor_kind,
        context.actor_key,
        context.user_id,
        "workspace.menus.updated",
        "workspace",
        str(context.workspace_id),
        {
            "menuCount": len(payload.menu_ids),
            "sidebarMode": payload.sidebar_mode,
            "version": response["version"],
        },
    )
    return response
