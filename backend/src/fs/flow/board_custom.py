"""보드 범위 자유 열·셀과 복구 가능한 그룹 작업. 공통 엔진의 TX/잠금 안에서 실행."""

import json
from datetime import UTC, date, datetime
from math import isfinite

from sqlalchemy import text

from fs.common.errors import ApiError

S = "workspace_id=:w AND generation_id=:g AND board_id=:b"
BUILTINS = [
    ("assignee", "담당자"),
    ("status", "상태"),
    ("timeline", "일정"),
    ("progress", "진행률"),
    ("priority", "중요도"),
    ("description", "설명"),
]


def defaults(c, sc, bid):
    for i, (key, name) in enumerate(BUILTINS):
        c.execute(
            text(
                "INSERT INTO flow.work_column(workspace_id,generation_id,board_id,name,kind,builtin_key,position) VALUES(:w,:g,:b,:name,'BUILTIN',:key,:position) ON CONFLICT(workspace_id,generation_id,board_id,builtin_key) DO NOTHING"
            ),
            {
                "w": sc.workspace_id,
                "g": sc.generation_id,
                "b": bid,
                "name": name,
                "key": key,
                "position": i,
            },
        )


def change(c, sc, op, body):
    p = {"w": sc.workspace_id, "g": sc.generation_id, "b": body["boardId"]}

    def get(table, id):
        row = (
            c.execute(
                text(f"SELECT * FROM flow.{table} WHERE {S} AND id=:id"),
                {**p, "id": id},
            )
            .mappings()
            .first()
        )
        if not row:
            raise ApiError(404, "NOT_FOUND", "이 보드의 항목이 없습니다.")
        return dict(row)

    def version(row, expected):
        if row["version"] != expected:
            raise ApiError(
                409, "VERSION_CONFLICT", "다른 사용자가 변경했습니다. 새로 조회하세요."
            )

    def insert(table, values):
        values = {
            "workspace_id": sc.workspace_id,
            "generation_id": sc.generation_id,
            "board_id": body["boardId"],
            **values,
        }
        return c.execute(
            text(
                f"INSERT INTO flow.{table} ({','.join(values)}) VALUES ({','.join(':' + k for k in values)}) RETURNING id"
            ),
            values,
        ).scalar_one()

    def update(table, row, values):
        c.execute(
            text(
                f"UPDATE flow.{table} SET {','.join(k + '=:' + k for k in values)},version=version+1 WHERE {S} AND id=:id"
            ),
            {**p, "id": row["id"], **values},
        )

    def active(row):
        if row.get("archived_at") or row.get("deleted_at"):
            raise ApiError(409, "ARCHIVED", "보관·삭제된 항목을 먼저 복구하세요.")

    if op.startswith("group-"):
        group = get("work_group", body["id"])
        version(group, body["version"])
        if op == "group-state":
            state = body["state"]
            update(
                "work_group",
                group,
                {
                    "archived_at": datetime.now(UTC) if state == "archive" else None,
                    "deleted_at": datetime.now(UTC) if state == "delete" else None,
                },
            )
            return "work_group", group["id"]
        active(group)
        tasks = (
            c.execute(
                text(
                    f"SELECT * FROM flow.work_task WHERE {S} AND group_id=:id AND archived_at IS NULL ORDER BY parent_id NULLS FIRST,position,id"
                ),
                {**p, "id": group["id"]},
            )
            .mappings()
            .all()
        )
        if len(tasks) > 500:
            raise ApiError(422, "GROUP_LIMIT", "복제는 500개 업무까지 가능합니다.")
        gid = insert(
            "work_group",
            {
                "name": (group["name"] + " 복사")[:120],
                "color": group["color"],
                "position": group["position"] + 1,
            },
        )
        ids = {}
        for task in tasks:
            values = {
                k: task[k]
                for k in (
                    "title",
                    "description",
                    "status",
                    "priority",
                    "starts_on",
                    "ends_on",
                    "progress",
                    "position",
                )
            }
            ids[task["id"]] = insert(
                "work_task",
                {**values, "group_id": gid, "parent_id": ids.get(task["parent_id"])},
            )
            for a in c.execute(
                text(
                    "SELECT user_id,display_name FROM flow.work_task_assignee WHERE workspace_id=:w AND generation_id=:g AND task_id=:id"
                ),
                {**p, "id": task["id"]},
            ).mappings():
                c.execute(
                    text(
                        "INSERT INTO flow.work_task_assignee(workspace_id,generation_id,task_id,user_id,display_name) VALUES(:w,:g,:task,:user,:name)"
                    ),
                    {
                        **p,
                        "task": ids[task["id"]],
                        "user": a["user_id"],
                        "name": a["display_name"],
                    },
                )
            for cell in c.execute(
                text(
                    f"SELECT column_id,kind,value FROM flow.work_cell WHERE {S} AND task_id=:id"
                ),
                {**p, "id": task["id"]},
            ).mappings():
                insert(
                    "work_cell",
                    {
                        "task_id": ids[task["id"]],
                        "column_id": cell["column_id"],
                        "kind": cell["kind"],
                        "value": json.dumps(cell["value"]),
                    },
                )
        return "work_group", gid
    if op.startswith("column-"):
        if op == "column-create":
            count = c.execute(
                text(
                    f"SELECT count(*) FROM flow.work_column WHERE {S} AND kind<>'BUILTIN' AND deleted_at IS NULL"
                ),
                p,
            ).scalar_one()
            if count >= 30:
                raise ApiError(
                    422, "COLUMN_LIMIT", "자유 열은 보드당 30개까지 가능합니다."
                )
            column = None
        else:
            column = get("work_column", body["id"])
            version(column, body["version"])
            if column["kind"] == "BUILTIN":
                raise ApiError(
                    422, "BUILTIN_COLUMN", "기본 열은 보기 설정에서 관리하세요."
                )
        if op == "column-state":
            state = body["state"]
            update(
                "work_column",
                column,
                {
                    "archived_at": datetime.now(UTC) if state == "archive" else None,
                    "deleted_at": datetime.now(UTC) if state == "delete" else None,
                },
            )
            return "work_column", column["id"]
        if column:
            active(column)
            if body["kind"] != column["kind"]:
                raise ApiError(
                    422, "COLUMN_KIND", "값 보존을 위해 열 유형은 변경할 수 없습니다."
                )
        options = body["options"]
        labels = options.get("labels", [])
        if body["kind"] == "STATUS" and (
            not isinstance(labels, list)
            or not 1 <= len(labels) <= 30
            or any(
                not isinstance(x, str) or not x.strip() or len(x) > 120 for x in labels
            )
            or len(set(labels)) != len(labels)
        ):
            raise ApiError(
                422, "COLUMN_OPTIONS", "중복 없는 상태 이름을 1~30개 지정하세요."
            )
        if len(json.dumps(options)) > 8000:
            raise ApiError(422, "COLUMN_OPTIONS", "열 설정이 너무 큽니다.")
        values = {
            "name": body["name"],
            "kind": body["kind"],
            "position": body["position"],
            "width": body["width"],
            "options": json.dumps(options),
        }
        if column:
            if body["kind"] == "STATUS":
                old_values = (
                    c.execute(
                        text(
                            f"SELECT value FROM flow.work_cell WHERE {S} AND column_id=:id"
                        ),
                        {**p, "id": column["id"]},
                    )
                    .scalars()
                    .all()
                )
                if any(x is not None and x not in labels for x in old_values):
                    raise ApiError(
                        409,
                        "STATUS_IN_USE",
                        "사용 중인 상태 이름은 먼저 셀에서 변경하세요.",
                    )
            update("work_column", column, values)
            return "work_column", column["id"]
        return "work_column", insert("work_column", values)
    task = get("work_task", body["taskId"])
    column = get("work_column", body["columnId"])
    version(task, body["taskVersion"])
    version(column, body["columnVersion"])
    active(task)
    active(get("work_group", task["group_id"]))
    active(column)
    kind, value = column["kind"], body["value"]
    valid = value is None
    if value is not None:
        if kind == "TEXT":
            valid = isinstance(value, str) and len(value) <= 4000
        elif kind == "NUMBER":
            valid = type(value) in (int, float) and isfinite(value)
        elif kind == "CHECKBOX":
            valid = type(value) is bool
        elif kind == "STATUS":
            valid = isinstance(value, str) and value in column["options"].get(
                "labels", []
            )
        elif kind in ("DATE", "TIMELINE"):
            try:
                if kind == "DATE":
                    date.fromisoformat(value)
                    valid = len(value) == 10
                else:
                    start, end = (
                        date.fromisoformat(value["start"]),
                        date.fromisoformat(value["end"]),
                    )
                    valid = (
                        set(value) == {"start", "end"}
                        and start <= end
                        and len(value["start"]) == len(value["end"]) == 10
                    )
            except ValueError, TypeError, KeyError:
                valid = False
    if kind == "BUILTIN" or not valid:
        raise ApiError(422, "CELL_VALUE", "열 유형에 맞는 값을 입력하세요.")
    old = (
        c.execute(
            text(
                f"SELECT * FROM flow.work_cell WHERE {S} AND task_id=:task AND column_id=:column"
            ),
            {**p, "task": task["id"], "column": column["id"]},
        )
        .mappings()
        .first()
    )
    if old:
        version(old, body["version"])
        update(
            "work_cell",
            old,
            {"value": json.dumps(value), "updated_at": datetime.now(UTC)},
        )
        eid = old["id"]
    else:
        if body["version"]:
            raise ApiError(409, "VERSION_CONFLICT", "셀을 다시 조회하세요.")
        eid = insert(
            "work_cell",
            {
                "task_id": task["id"],
                "column_id": column["id"],
                "kind": kind,
                "value": json.dumps(value),
            },
        )
    return "work_cell", eid
