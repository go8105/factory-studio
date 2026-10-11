"""회사 공동 업무 보드. 실제 계정/회사 멤버십만 사용한다."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.core.company import companies, members, resolve_company

S = "workspace_id=:w AND generation_id=:g"


def params(ctx):
    return {"w": ctx.workspace_id, "g": ctx.generation_id, "u": ctx.user_id}


def rows(c, ctx, table, where="", extra=None):
    return [
        dict(r)
        for r in c.execute(
            text(f"SELECT * FROM flow.{table} WHERE {S} {where}"),
            {**params(ctx), **(extra or {})},
        ).mappings()
    ]


def principal(c, ctx):
    resolve_company(c, ctx, ctx.workspace_id)
    people = members(c, ctx)
    return next(p for p in people if p["id"] == ctx.user_id and p["active"]), people


def board(c, ctx, bid, level="VIEWER", archived=False):
    person, _ = principal(c, ctx)
    found = rows(c, ctx, "work_board", "AND id=:id", {"id": bid})
    if not found:
        raise ApiError(404, "NOT_FOUND", "보드가 없습니다.")
    b = found[0]
    roles = rows(
        c, ctx, "work_board_member", "AND board_id=:id AND user_id=:u", {"id": bid}
    )
    role = roles[0]["role"] if roles else "VIEWER"
    # 회사 소유자는 복구/역할 관리만 가능; 일반 편집 권한은 보드 역할로 판단한다.
    if level == "OWNER" and person["role"] == "OWNER":
        role = "OWNER"
    if (level == "EDITOR" and role not in ("EDITOR", "OWNER")) or (
        level == "OWNER" and role != "OWNER"
    ):
        raise ApiError(403, "BOARD_ACCESS_DENIED", "보드 편집 권한이 없습니다.")
    if b["archived_at"] and not archived:
        raise ApiError(409, "BOARD_ARCHIVED", "보관된 보드입니다.")
    return b, role


def company_list(ctx):
    with read() as c:
        return companies(c, ctx)


def overview(ctx, cid, bid=None, offset=0, limit=50, search="", status="", mine=False):
    with read() as c:
        sc, company = resolve_company(c, ctx, cid)
        sc = read_scope(c, sc, "flow")
        person, people = principal(c, sc)
        boards = rows(c, sc, "work_board", "ORDER BY id DESC")
        favorites = rows(
            c, sc, "work_board_favorite", "AND user_id=:u ORDER BY position,id"
        )
        settings = rows(c, sc, "work_project_settings")
        result = {
            "company": company,
            "userId": sc.user_id,
            "companyOwner": person["role"] == "OWNER",
            "members": people,
            "boards": boards,
            "favorites": [r["board_id"] for r in favorites],
            "allowCreate": settings[0]["allow_create"] if settings else True,
        }
        if bid:
            b, role = board(c, sc, bid, archived=True)
            # 부모 단위 페이지: 부모와 그 하위 업무를 같은 페이지에 담아 집계를 보존한다.
            matches = f"""SELECT DISTINCT COALESCE(t.parent_id,t.id) root FROM flow.work_task t
              WHERE t.{S.replace(" AND ", " AND t.")} AND t.board_id=:id
                AND (:search='' OR strpos(lower(t.title),lower(:search))>0)
                AND (:status='' OR t.status=:status)
                AND (NOT :mine OR EXISTS(SELECT 1 FROM flow.work_task_assignee a WHERE
                  (a.workspace_id,a.generation_id,a.task_id,a.user_id)=(t.workspace_id,t.generation_id,t.id,:u)))"""
            query = {
                **params(sc),
                "id": bid,
                "offset": offset,
                "limit": limit,
                "search": search,
                "status": status,
                "mine": mine,
            }
            root_count = c.execute(
                text(f"SELECT count(*) FROM ({matches}) matched"), query
            ).scalar_one()
            root_ids = (
                c.execute(
                    text(
                        f"SELECT id FROM flow.work_task WHERE {S} AND board_id=:id AND parent_id IS NULL AND id IN ({matches}) ORDER BY position,id LIMIT :limit OFFSET :offset"
                    ),
                    query,
                )
                .scalars()
                .all()
            )
            tasks = (
                rows(
                    c,
                    sc,
                    "work_task",
                    "AND board_id=:id AND (id=ANY(:roots) OR parent_id=ANY(:roots)) ORDER BY position,id",
                    {"id": bid, "roots": root_ids},
                )
                if root_ids
                else []
            )
            result["nextOffset"] = (
                offset + len(root_ids) if offset + len(root_ids) < root_count else None
            )
            result["rootCount"] = root_count
            assignees = [
                dict(r)
                for r in c.execute(
                    text(
                        f"SELECT a.* FROM flow.work_task_assignee a JOIN flow.work_task t ON (a.workspace_id,a.generation_id,a.task_id)=(t.workspace_id,t.generation_id,t.id) WHERE t.{S.replace(' AND ', ' AND t.')} AND t.board_id=:id AND t.id=ANY(:task_ids)"
                    ),
                    {**params(sc), "id": bid, "task_ids": [t["id"] for t in tasks]},
                ).mappings()
            ]
            active = {p["id"]: p["active"] for p in people}
            assigned = {}
            for a in assignees:
                assigned.setdefault(a["task_id"], []).append(
                    {**a, "active": active.get(a["user_id"], False)}
                )
            for t in tasks:
                t["assignees"] = assigned.get(t["id"], [])
            aggregate(tasks)
            result.update(
                boardMembers=rows(
                    c, sc, "work_board_member", "AND board_id=:id", {"id": bid}
                ),
                board=b,
                role=role,
                groups=rows(
                    c,
                    sc,
                    "work_group",
                    "AND board_id=:id ORDER BY position,id",
                    {"id": bid},
                ),
                columns=rows(
                    c,
                    sc,
                    "work_column",
                    "AND board_id=:id ORDER BY position,id",
                    {"id": bid},
                ),
                cells=rows(
                    c,
                    sc,
                    "work_cell",
                    "AND board_id=:id AND task_id=ANY(:ids)",
                    {"id": bid, "ids": [t["id"] for t in tasks]},
                ),
                tasks=tasks,
                preference=rows(
                    c,
                    sc,
                    "work_view_preference",
                    "AND board_id=:id AND user_id=:u",
                    {"id": bid},
                ),
            )
        return jsonable_encoder(result)


def aggregate(tasks):
    by_parent = {}
    for t in tasks:
        if t["parent_id"] and not t["archived_at"]:
            by_parent.setdefault(t["parent_id"], []).append(t)
    for parent in tasks:
        children = by_parent.get(parent["id"], [])
        parent["aggregate"] = bool(children)
        if not children:
            continue
        valid = [t for t in children if t["status"] != "CANCELLED"]
        parent["progress"] = (
            round(sum(t["progress"] for t in valid) / len(valid)) if valid else 0
        )
        pending = [t for t in valid if t["status"] != "DONE"]
        parent["status"] = (
            "CANCELLED"
            if not valid
            else "DONE"
            if not pending
            else "WAITING"
            if all(t["status"] == "WAITING" for t in valid)
            else "BLOCKED"
            if all(t["status"] == "BLOCKED" for t in pending)
            else "REVIEW"
            if all(t["status"] == "REVIEW" for t in pending)
            else "WORKING"
        )
        for field, fn in [("starts_on", min), ("ends_on", max)]:
            values = [t[field] for t in children if t[field]]
            parent[field] = fn(values) if values else None


def detail(ctx, cid, bid, tid, offset=0):
    with read() as c:
        sc, _ = resolve_company(c, ctx, cid)
        sc = read_scope(c, sc, "flow")
        board(c, sc, bid, archived=True)
        task = rows(
            c, sc, "work_task", "AND board_id=:b AND id=:id", {"b": bid, "id": tid}
        )
        if not task:
            raise ApiError(404, "NOT_FOUND", "업무가 없습니다.")
        return jsonable_encoder(
            {
                "comments": rows(
                    c,
                    sc,
                    "work_task_comment",
                    "AND task_id=:id ORDER BY id DESC LIMIT 50 OFFSET :offset",
                    {"id": tid, "offset": offset},
                ),
                "events": rows(
                    c,
                    sc,
                    "work_task_event",
                    "AND task_id=:id ORDER BY id DESC LIMIT 50 OFFSET :offset",
                    {"id": tid, "offset": offset},
                ),
            }
        )


def my_tasks(ctx, cid):
    with read() as c:
        sc, company = resolve_company(c, ctx, cid)
        sc = read_scope(c, sc, "flow")
        _, people = principal(c, sc)
        tasks = [
            dict(r)
            for r in c.execute(
                text(f"""SELECT t.*,b.name AS board_name FROM flow.work_task t JOIN flow.work_board b ON (t.workspace_id,t.generation_id,t.board_id)=(b.workspace_id,b.generation_id,b.id)
        JOIN flow.work_task_assignee a ON (t.workspace_id,t.generation_id,t.id)=(a.workspace_id,a.generation_id,a.task_id)
        WHERE t.{S.replace(" AND ", " AND t.")} AND a.user_id=:u AND t.archived_at IS NULL AND b.archived_at IS NULL
        AND EXISTS(SELECT 1 FROM flow.work_group gr WHERE (gr.workspace_id,gr.generation_id,gr.id)=(t.workspace_id,t.generation_id,t.group_id) AND gr.archived_at IS NULL AND gr.deleted_at IS NULL)
        AND NOT EXISTS(SELECT 1 FROM flow.work_task ch WHERE (ch.workspace_id,ch.generation_id,ch.parent_id)=(t.workspace_id,t.generation_id,t.id) AND ch.archived_at IS NULL)
        ORDER BY t.ends_on NULLS LAST,t.id LIMIT 1000"""),
                params(sc),
            ).mappings()
        ]
        assignees = rows(
            c,
            sc,
            "work_task_assignee",
            "AND task_id=ANY(:ids)",
            {"ids": [t["id"] for t in tasks]},
        )
        active = {p["id"]: p["active"] for p in people}
        assigned = {}
        for a in assignees:
            assigned.setdefault(a["task_id"], []).append(
                {**a, "active": active.get(a["user_id"], False)}
            )
        today = datetime.now(ZoneInfo(company["timezone"])).date()
        for t in tasks:
            t["assignees"] = assigned.get(t["id"], [])
            t["overdue"] = bool(
                t["ends_on"]
                and t["ends_on"] < today
                and t["status"] not in ("DONE", "CANCELLED")
            )
        return jsonable_encoder(tasks)


def mutate(ctx, cid, op, key, body):
    with read() as c:
        sc, _ = resolve_company(c, ctx, cid)
        sc = read_scope(c, sc, "flow")
    bid = body.get("boardId")
    personal = op in ("favorite", "preference")
    owner = op in ("board-update", "member", "settings") or op.startswith(
        ("column-", "group-")
    )

    def authorize(c, sc):
        p, _ = principal(c, sc)
        if op == "settings" and p["role"] != "OWNER":
            raise ApiError(403, "FORBIDDEN", "회사 소유자만 설정할 수 있습니다.")
        if bid:
            board(
                c,
                sc,
                bid,
                "VIEWER" if personal else "OWNER" if owner else "EDITOR",
                archived=op in ("board-update", "member", "favorite", "preference"),
            )
        if op == "board-create":
            settings = rows(c, sc, "work_project_settings")
            if settings and not settings[0]["allow_create"] and p["role"] != "OWNER":
                raise ApiError(403, "FORBIDDEN", "보드 생성이 제한되어 있습니다.")

    def run(c, sc):
        p = params(sc)

        def insert(table, values):
            values = {
                "workspace_id": sc.workspace_id,
                "generation_id": sc.generation_id,
                **values,
            }
            return c.execute(
                text(
                    f"INSERT INTO flow.{table} ({','.join(values)}) VALUES ({','.join(':' + k for k in values)}) RETURNING id"
                ),
                values,
            ).scalar_one()

        def update(table, id, values, version):
            count = c.execute(
                text(
                    f"UPDATE flow.{table} SET {','.join(k + '=:' + k for k in values)},version=version+1 WHERE {S} AND id=:id AND version=:version"
                ),
                {**p, **values, "id": id, "version": version},
            ).rowcount
            if count != 1:
                raise ApiError(
                    409,
                    "VERSION_CONFLICT",
                    "다른 사용자가 변경했습니다. 새로 조회하고 확인해 주세요.",
                )

        before = None
        entity = "work_board"
        eid = bid or sc.workspace_id
        tid = None
        if op in ("task-update", "comment-create", "comment-update"):
            target_id = body.get("taskId", body.get("id"))
            existing = rows(
                c,
                sc,
                "work_task",
                "AND board_id=:b AND id=:id",
                {"b": bid, "id": target_id},
            )
            if existing and not rows(
                c,
                sc,
                "work_group",
                "AND board_id=:b AND id=:id AND archived_at IS NULL AND deleted_at IS NULL",
                {"b": bid, "id": existing[0]["group_id"]},
            ):
                raise ApiError(409, "ARCHIVED", "그룹을 먼저 복구하세요.")
        if op == "board-create":
            eid = insert(
                "work_board",
                {
                    "name": body["name"].strip(),
                    "description": body.get("description", ""),
                    "template": body["template"],
                },
            )
            insert(
                "work_board_member",
                {"board_id": eid, "user_id": sc.user_id, "role": "OWNER"},
            )
            for i, name in enumerate(
                {
                    "PROJECT": ["계획·검토", "실행·검증"],
                    "TEAM": ["이번 주", "다음 주"],
                    "ISSUE": ["접수", "처리"],
                    "MEETING": ["후속 업무"],
                }[body["template"]]
            ):
                insert("work_group", {"board_id": eid, "name": name, "position": i})
            from fs.flow.board_custom import defaults

            defaults(c, sc, eid)
        elif op in (
            "group-state",
            "group-duplicate",
            "column-create",
            "column-update",
            "column-state",
            "cell-update",
            "cell-batch-update",
        ):
            from fs.flow.board_custom import change

            entity, eid = change(c, sc, op, body)
        elif op == "board-update":
            update(
                "work_board",
                bid,
                {
                    "name": body["name"].strip(),
                    "description": body.get("description", ""),
                    "archived_at": datetime.now(ZoneInfo("UTC"))
                    if body["archived"]
                    else None,
                },
                body["version"],
            )
        elif op == "settings":
            c.execute(
                text(
                    "INSERT INTO flow.work_project_settings(workspace_id,generation_id,allow_create) VALUES(:w,:g,:allow) ON CONFLICT(workspace_id,generation_id) DO UPDATE SET allow_create=:allow,version=flow.work_project_settings.version+1"
                ),
                {**p, "allow": body["allowCreate"]},
            )
        elif op == "member":
            _, people = principal(c, sc)
            target = next(
                (x for x in people if x["id"] == body["userId"] and x["active"]), None
            )
            if not target:
                raise ApiError(422, "INVALID_ASSIGNEE", "활성 회사 계정을 선택하세요.")
            owners = rows(
                c,
                sc,
                "work_board_member",
                "AND board_id=:b AND role='OWNER'",
                {"b": bid},
            )
            active = {x["id"] for x in people if x["active"]}
            if (
                body["role"] != "OWNER"
                and any(o["user_id"] == body["userId"] for o in owners)
                and not any(
                    o["user_id"] in active and o["user_id"] != body["userId"]
                    for o in owners
                )
            ):
                raise ApiError(409, "LAST_OWNER", "다른 활성 소유자를 먼저 지정하세요.")
            c.execute(
                text(
                    f"DELETE FROM flow.work_board_member WHERE {S} AND board_id=:b AND user_id=:target"
                ),
                {**p, "b": bid, "target": body["userId"]},
            )
            if body["role"] != "VIEWER":
                insert(
                    "work_board_member",
                    {"board_id": bid, "user_id": body["userId"], "role": body["role"]},
                )
        elif op.startswith("group-"):
            entity = "work_group"
            if op == "group-create":
                eid = insert(
                    entity,
                    {
                        "board_id": bid,
                        "name": body["name"].strip(),
                        "color": body["color"],
                        "position": body["position"],
                    },
                )
            else:
                group = rows(
                    c,
                    sc,
                    entity,
                    "AND board_id=:b AND id=:id",
                    {"b": bid, "id": body["id"]},
                )
                if not group:
                    raise ApiError(404, "NOT_FOUND", "그룹이 없습니다.")
                before = group[0]
                new_position = body["position"]
                groups = rows(
                    c,
                    sc,
                    "work_group",
                    "AND board_id=:b ORDER BY position,id",
                    {"b": bid},
                )
                index = next(i for i, x in enumerate(groups) if x["id"] == body["id"])
                target = (
                    index - 1
                    if new_position < before["position"]
                    else index + 1
                    if new_position > before["position"]
                    else index
                )
                if 0 <= target < len(groups) and target != index:
                    other = groups[target]
                    update(
                        "work_group",
                        other["id"],
                        {"position": before["position"]},
                        other["version"],
                    )
                    new_position = other["position"]
                else:
                    new_position = before["position"]
                eid = body["id"]
                update(
                    entity,
                    eid,
                    {
                        "name": body["name"],
                        "color": body["color"],
                        "position": new_position,
                    },
                    body["version"],
                )
        elif op in ("task-create", "task-update"):
            entity = "work_task"
            tid = body.get("id")
            parent = body.get("parentId")
            group = rows(
                c,
                sc,
                "work_group",
                "AND board_id=:b AND id=:id AND archived_at IS NULL AND deleted_at IS NULL",
                {"b": bid, "id": body["groupId"]},
            )
            if not group:
                raise ApiError(422, "INVALID_GROUP", "이 보드의 그룹을 선택하세요.")
            if parent:
                pr = rows(
                    c,
                    sc,
                    entity,
                    "AND board_id=:b AND group_id=:group AND id=:id AND archived_at IS NULL",
                    {"b": bid, "group": body["groupId"], "id": parent},
                )
                if not pr or pr[0]["parent_id"] or parent == tid:
                    raise ApiError(
                        422,
                        "INVALID_PARENT",
                        "같은 그룹의 최상위 업무만 선택할 수 있습니다.",
                    )
            status = body["status"]
            progress = (
                100
                if status == "DONE"
                else min(body["progress"], 99)
                if status != "CANCELLED"
                else body["progress"]
            )
            values = {
                "board_id": bid,
                "group_id": body["groupId"],
                "parent_id": parent,
                "title": body["title"].strip(),
                "description": body["description"],
                "status": status,
                "priority": body["priority"],
                "starts_on": date.fromisoformat(body["startsOn"])
                if body.get("startsOn")
                else None,
                "ends_on": date.fromisoformat(body["endsOn"])
                if body.get("endsOn")
                else None,
                "progress": progress,
                "position": body["position"],
                "archived_at": datetime.now(ZoneInfo("UTC"))
                if body["archived"]
                else None,
            }
            if (
                values["starts_on"]
                and values["ends_on"]
                and values["starts_on"] > values["ends_on"]
            ):
                raise ApiError(
                    422, "INVALID_DATES", "시작일은 종료일보다 늦을 수 없습니다."
                )
            if tid:
                current = rows(
                    c, sc, entity, "AND board_id=:b AND id=:id", {"b": bid, "id": tid}
                )
                if not current:
                    raise ApiError(404, "NOT_FOUND", "업무가 없습니다.")
                before = current[0]
                children = rows(c, sc, entity, "AND parent_id=:id", {"id": tid})
                if children:
                    if parent:
                        raise ApiError(
                            422,
                            "INVALID_PARENT",
                            "하위 업무가 있는 업무는 하위 업무로 옮길 수 없습니다.",
                        )
                    for field in ("status", "progress", "starts_on", "ends_on"):
                        values[field] = current[0][field]
                    if values["group_id"] != current[0]["group_id"]:
                        raise ApiError(
                            422,
                            "INVALID_GROUP",
                            "하위 업무가 있는 업무의 그룹 이동은 제한됩니다.",
                        )
                    # 부모 보관 시 자식 함께 보관; 복구도 같은 범위에서 수행.
                    if bool(values["archived_at"]) != bool(current[0]["archived_at"]):
                        predicate = (
                            "archived_at IS NULL"
                            if values["archived_at"]
                            else "archived_at=:previous_archive"
                        )
                        c.execute(
                            text(
                                f"UPDATE flow.work_task SET archived_at=:a,version=version+1 WHERE {S} AND parent_id=:id AND {predicate}"
                            ),
                            {
                                **p,
                                "id": tid,
                                "a": values["archived_at"],
                                "previous_archive": current[0]["archived_at"],
                            },
                        )
                update(entity, tid, values, body["version"])
                eid = tid
            else:
                eid = insert(entity, values)
                tid = eid
            _, people = principal(c, sc)
            active = {x["id"]: x["name"] for x in people if x["active"]}
            users = body["assignees"]
            old = rows(c, sc, "work_task_assignee", "AND task_id=:id", {"id": tid})
            preserved = {x["user_id"]: x["display_name"] for x in old}
            if any(u not in active and u not in preserved for u in users):
                raise ApiError(
                    422, "INVALID_ASSIGNEE", "활성 회사 계정만 새로 배정할 수 있습니다."
                )
            c.execute(
                text(f"DELETE FROM flow.work_task_assignee WHERE {S} AND task_id=:id"),
                {**p, "id": tid},
            )
            for u in set(users):
                insert(
                    "work_task_assignee",
                    {
                        "task_id": tid,
                        "user_id": u,
                        "display_name": active.get(u, preserved.get(u, "")),
                    },
                )
            if parent:
                c.execute(
                    text(
                        f"UPDATE flow.work_task SET version=version+1 WHERE {S} AND id=:id"
                    ),
                    {**p, "id": parent},
                )
        elif op.startswith("comment-"):
            entity = "work_task_comment"
            tid = body["taskId"]
            if not rows(
                c,
                sc,
                "work_task",
                "AND board_id=:b AND id=:id AND archived_at IS NULL",
                {"b": bid, "id": tid},
            ):
                raise ApiError(404, "NOT_FOUND", "업무가 없습니다.")
            if op == "comment-create":
                eid = insert(
                    entity,
                    {
                        "task_id": tid,
                        "user_id": sc.user_id,
                        "body": body["body"].strip(),
                    },
                )
            else:
                old = rows(
                    c,
                    sc,
                    entity,
                    "AND id=:id AND task_id=:t AND user_id=:u",
                    {"id": body["id"], "t": tid},
                )
                if not old:
                    raise ApiError(
                        403, "FORBIDDEN", "자신의 댓글만 수정할 수 있습니다."
                    )
                before = old[0]
                eid = body["id"]
                update(
                    entity,
                    eid,
                    {
                        "body": body["body"].strip(),
                        "updated_at": datetime.now(ZoneInfo("UTC")),
                        "deleted_at": datetime.now(ZoneInfo("UTC"))
                        if body["deleted"]
                        else None,
                    },
                    body["version"],
                )
        elif op in ("favorite", "preference"):
            entity = (
                "work_board_favorite" if op == "favorite" else "work_view_preference"
            )
            c.execute(
                text(
                    f"DELETE FROM flow.{entity} WHERE {S} AND board_id=:b AND user_id=:u"
                ),
                {**p, "b": bid},
            )
            if op == "preference" or body["selected"]:
                values = {"board_id": bid, "user_id": sc.user_id}
                if op == "preference":
                    import json

                    values["settings"] = json.dumps(body["settings"])
                eid = insert(entity, values)
        else:
            raise ApiError(422, "INVALID_OPERATION", "지원하지 않는 작업입니다.")
        if not personal:
            import json

            insert(
                "work_task_event",
                {
                    "board_id": bid or eid,
                    "task_id": tid,
                    "user_id": sc.user_id,
                    "action": op,
                    "details": json.dumps(
                        {"request": body, "before": jsonable_encoder(before)},
                        ensure_ascii=False,
                    ),
                },
            ) if op != "settings" else None
        return {"id": eid}, "flow." + entity, eid

    return action("flow", sc, "gw.projects." + op, key, body, run, authorize=authorize)
