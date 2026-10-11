"""별도 회사 프로젝트 API: 체험 시드/담당자 선택 의존성 없음."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.flow import projects

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
Company = Annotated[int, Query(alias="companyId", gt=0)]
Csrf = Annotated[str | None, Header(alias="X-CSRF-Token")]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoardCreate(Body):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)
    template: Literal["PROJECT", "TEAM", "ISSUE", "MEETING"] = "PROJECT"

    @field_validator("name")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("이름을 입력하세요.")
        return v.strip()


class BoardUpdate(BoardCreate):
    boardId: int = Field(gt=0)
    version: int = Field(gt=0)
    archived: bool = False


class BoardId(Body):
    boardId: int = Field(gt=0)


class Member(BoardId):
    userId: int = Field(gt=0)
    role: Literal["VIEWER", "EDITOR", "OWNER"]


class Settings(Body):
    allowCreate: bool


class GroupCreate(BoardId):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#40566b", pattern=r"^#[0-9a-fA-F]{6}$")
    position: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("이름을 입력하세요.")
        return v.strip()


class GroupUpdate(GroupCreate):
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class EntityState(BoardId):
    id: int = Field(gt=0)
    version: int = Field(gt=0)
    state: Literal["archive", "delete", "restore"]


class GroupDuplicate(BoardId):
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class ColumnCreate(BoardId):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["TEXT", "NUMBER", "DATE", "STATUS", "CHECKBOX", "TIMELINE"]
    position: int = Field(default=0, ge=0)
    width: int = Field(default=160, ge=80, le=600)
    options: dict = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("열 이름을 입력하세요.")
        return v.strip()


class ColumnUpdate(ColumnCreate):
    kind: Literal["BUILTIN", "TEXT", "NUMBER", "DATE", "STATUS", "CHECKBOX", "TIMELINE"]
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class CellUpdate(BoardId):
    taskId: int = Field(gt=0)
    taskVersion: int = Field(gt=0)
    columnId: int = Field(gt=0)
    columnVersion: int = Field(gt=0)
    version: int = Field(default=0, ge=0)
    value: str | int | float | bool | dict | None


class CellBatch(BoardId):
    cells: list[CellUpdate] = Field(min_length=1, max_length=100)

    @field_validator("cells")
    @classmethod
    def unique_cells(cls, cells):
        if len({(x.taskId, x.columnId) for x in cells}) != len(cells):
            raise ValueError("동일 셀은 한 번만 지정하세요.")
        return cells


class TaskCreate(BoardId):
    groupId: int = Field(gt=0)
    parentId: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(default="", max_length=10000)
    status: Literal["WAITING", "WORKING", "REVIEW", "BLOCKED", "DONE", "CANCELLED"] = (
        "WAITING"
    )
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"] = "NORMAL"
    startsOn: date | None = None
    endsOn: date | None = None
    progress: int = Field(default=0, ge=0, le=100)
    position: int = Field(default=0, ge=0)
    archived: bool = False
    assignees: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("제목을 입력하세요.")
        return v.strip()


class TaskUpdate(TaskCreate):
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class CommentCreate(BoardId):
    taskId: int = Field(gt=0)
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("내용을 입력하세요.")
        return v.strip()


class CommentUpdate(CommentCreate):
    id: int = Field(gt=0)
    version: int = Field(gt=0)
    deleted: bool = False


class Favorite(BoardId):
    selected: bool


class ViewSettings(Body):
    view: Literal["table", "kanban", "calendar", "gantt"] = "table"
    search: str = Field(default="", max_length=250)
    status: Literal[
        "", "WAITING", "WORKING", "REVIEW", "BLOCKED", "DONE", "CANCELLED"
    ] = ""
    mine: bool = False
    sort: Literal["position", "due", "title"] = "position"
    hidden: list[Literal["assignees", "priority", "progress"]] = Field(
        default_factory=list
    )

    columns: list[Literal["assignees", "status", "priority", "dates", "progress"]] = (
        Field(
            default_factory=lambda: [
                "assignees",
                "status",
                "priority",
                "dates",
                "progress",
            ],
            min_length=5,
            max_length=5,
        )
    )

    @field_validator("columns")
    @classmethod
    def unique_columns(cls, v):
        if len(set(v)) != 5:
            raise ValueError("열은 각각 한 번씩 지정하세요.")
        return v


class Preference(BoardId):
    settings: ViewSettings


@router.get("/companies")
def companies(ctx: Auth):
    return {"data": projects.company_list(ctx)}


@router.get("")
def overview(
    ctx: Auth,
    cid: Company,
    boardId: int | None = Query(default=None, gt=0),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str = Query(default="", max_length=250),
    status: Literal[
        "", "WAITING", "WORKING", "REVIEW", "BLOCKED", "DONE", "CANCELLED"
    ] = "",
    mine: bool = False,
):
    return {
        "data": projects.overview(
            ctx, cid, boardId, offset, limit, search, status, mine
        )
    }


@router.get("/my-tasks")
def my_tasks(ctx: Auth, cid: Company):
    return {"data": projects.my_tasks(ctx, cid)}


@router.get("/detail")
def detail(
    ctx: Auth,
    cid: Company,
    boardId: int = Query(gt=0),
    taskId: int = Query(gt=0),
    offset: int = Query(default=0, ge=0),
):
    return {"data": projects.detail(ctx, cid, boardId, taskId, offset)}


# 각 경로에 명시적 Pydantic 스키마를 등록하여 임의 필드/동작을 차단한다.
def endpoint(operation, model):
    def run(body, ctx: Auth, cid: Company, csrf: Csrf = None, key: Key = None):
        return {
            "data": projects.mutate(
                ctx,
                cid,
                operation,
                mutation_key(ctx, csrf, key),
                body.model_dump(mode="json"),
            )
        }

    run.__annotations__["body"] = model
    router.add_api_route("/" + operation, run, methods=["POST"], name=operation)


for operation, model in [
    ("board-create", BoardCreate),
    ("board-update", BoardUpdate),
    ("member", Member),
    ("settings", Settings),
    ("group-create", GroupCreate),
    ("group-update", GroupUpdate),
    ("group-state", EntityState),
    ("group-duplicate", GroupDuplicate),
    ("column-create", ColumnCreate),
    ("column-update", ColumnUpdate),
    ("column-state", EntityState),
    ("cell-update", CellUpdate),
    ("cell-batch-update", CellBatch),
    ("task-create", TaskCreate),
    ("task-update", TaskUpdate),
    ("comment-create", CommentCreate),
    ("comment-update", CommentUpdate),
    ("favorite", Favorite),
    ("preference", Preference),
]:
    endpoint(operation, model)
