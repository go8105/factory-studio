"""GW-d collaboration policies, scoped reads and atomic notification delivery."""

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.gw import service as s


def missing():
    raise ApiError(404, "NOT_FOUND", "현재 담당자가 볼 수 있는 대상이 없습니다.")


def post_visible(row, person):
    return row["visibility"] == "WORKSPACE" or bool(
        person
        and person["is_active"]
        and (
            row["author_id"] == person["id"]
            or row["audience_org_id"] == person["organization_unit_id"]
        )
    )


def target(c, ctx, kind, id, person):
    row = s.one(c, ctx, "board_post" if kind == "POST" else "approval_document", id)
    if kind == "POST" and not post_visible(row, person):
        missing()
    return row


def notify(c, ctx, recipients, kind, ref_kind, ref_id, key, title):
    for recipient in set(recipients):
        c.execute(
            text("""INSERT INTO gw.notification(workspace_id,generation_id,recipient_id,kind,ref_kind,ref_id,event_key,title)
            SELECT :w,:g,id,:kind,:ref_kind,:ref_id,:key,:title FROM gw.person
            WHERE workspace_id=:w AND generation_id=:g AND id=:recipient AND is_active
            ON CONFLICT(workspace_id,generation_id,recipient_id,event_key) DO NOTHING"""),
            s.params(
                ctx,
                recipient=recipient,
                kind=kind,
                ref_kind=ref_kind,
                ref_id=ref_id,
                key=key,
                title=title[:200],
            ),
        )


def business_notifications(c, ctx, kind, before, after):
    if kind == "documents":
        id = after["id"]
        if after["status"] == "IN_REVIEW" and (
            not before
            or before["status"] != "IN_REVIEW"
            or before["current_step"] != after["current_step"]
        ):
            from fs.gw import policy

            people = s.rows(
                c, f"SELECT * FROM gw.person WHERE {s.S} AND is_active", s.params(ctx)
            )
            recipients = [p["id"] for p in people if policy.eligible(c, ctx, after, p)]
            notify(
                c,
                ctx,
                recipients,
                "APPROVAL_ARRIVED",
                "DOCUMENT",
                id,
                f"D:{id}:STAGE:{after['current_step']}",
                after["title"],
            )
        if (
            before
            and before["status"] == "IN_REVIEW"
            and after["status"] in {"APPROVED", "REJECTED", "WITHDRAWN"}
        ):
            recipients = [after["drafter_id"]]
            if after["status"] == "WITHDRAWN":
                recipients += [
                    p["person_id"]
                    for p in s.steps(c, ctx, id)
                    if p["seq"] == before["current_step"]
                ]
            notify(
                c,
                ctx,
                recipients,
                "APPROVAL_DONE" if after["status"] == "APPROVED" else after["status"],
                "DOCUMENT",
                id,
                f"D:{id}:CLOSED",
                after["title"],
            )
    elif (
        kind == "posts"
        and after["board_kind"] == "NOTICE"
        and after["status"] == "PUBLISHED"
        and (not before or before["status"] != "PUBLISHED")
    ):
        recipients = [
            p["id"]
            for p in s.rows(
                c, f"SELECT * FROM gw.person WHERE {s.S} AND is_active", s.params(ctx)
            )
            if post_visible(after, p)
        ]
        notify(
            c,
            ctx,
            recipients,
            "NOTICE",
            "POST",
            after["id"],
            f"P:{after['id']}:PUBLISHED",
            after["title"],
        )


def calendar_visible(c, ctx, row, person):
    if row["owner_id"] == person["id"] or (
        row["scope"] == "DEPARTMENT"
        and row["organization_unit_id"] == person["organization_unit_id"]
    ):
        return True
    return bool(
        s.rows(
            c,
            f"SELECT id FROM gw.event_attendee WHERE {s.S} AND event_id=:id AND person_id=:person",
            s.params(ctx, id=row["id"], person=person["id"]),
        )
    )


def calendar_detail(c, ctx, id, person):
    row = s.one(c, ctx, "calendar_event", id)
    if not calendar_visible(c, ctx, row, person):
        missing()
    row["attendees"] = s.rows(
        c,
        """SELECT a.*,p.name FROM gw.event_attendee a JOIN gw.person p ON
        (p.workspace_id,p.generation_id,p.id)=(a.workspace_id,a.generation_id,a.person_id)
        WHERE a.workspace_id=:w AND a.generation_id=:g AND a.event_id=:id ORDER BY a.id""",
        s.params(ctx, id=id),
    )
    row["owner_name"] = s.one(c, ctx, "person", row["owner_id"])["name"]
    row["organization_name"] = (
        s.one(c, ctx, "organization_unit", row["organization_unit_id"])["name"]
        if row["organization_unit_id"]
        else None
    )
    return row


def membership(c, ctx, id, person, lock=False):
    channel = s.one(c, ctx, "chat_channel", id, lock)
    members = s.rows(
        c,
        f"SELECT * FROM gw.chat_member WHERE {s.S} AND channel_id=:id AND person_id=:person AND left_at IS NULL",
        s.params(ctx, id=id, person=person["id"]),
    )
    if not members:
        missing()
    return channel, members[0]


def query(context, resource, person_id, **q):
    with s.read_transaction() as c:
        ctx = read_scope(c, context, "gw")
        person = s.actor(c, ctx, person_id)
        if resource == "comments":
            target(c, ctx, q["target_kind"], q["target_id"], person)
            column = "post_id" if q["target_kind"] == "POST" else "document_id"
            rows = s.rows(
                c,
                f"SELECT * FROM gw.comment WHERE {s.S} AND {column}=:id ORDER BY id OFFSET :offset LIMIT :limit",
                s.params(
                    ctx,
                    id=q["target_id"],
                    offset=q.get("offset", 0),
                    limit=q.get("limit", 50),
                ),
            )
            for row in rows:
                if row["status"] == "DELETED":
                    row["body"] = ""
                row["revisions"] = (
                    s.rows(
                        c,
                        f"SELECT revision_no,body,created_at FROM gw.comment_revision WHERE {s.S} AND comment_id=:id ORDER BY revision_no",
                        s.params(ctx, id=row["id"]),
                    )
                    if row["status"] == "ACTIVE"
                    else []
                )
            return s.wire(rows)
        if resource == "calendar":
            if q.get("id"):
                return s.wire(calendar_detail(c, ctx, q["id"], person))
            if (
                q["ends_at"] <= q["starts_at"]
                or (q["ends_at"] - q["starts_at"]).days > 93
            ):
                raise s.invalid("endsAt", "조회 기간은 1~93일로 지정하세요.")
            rows = s.rows(
                c,
                """SELECT e.* FROM gw.calendar_event e WHERE e.workspace_id=:w AND e.generation_id=:g
                AND starts_at<:end AND ends_at>:start AND (owner_id=:person OR (scope='DEPARTMENT' AND organization_unit_id=:org)
                OR EXISTS(SELECT 1 FROM gw.event_attendee a WHERE (a.workspace_id,a.generation_id,a.event_id)=(e.workspace_id,e.generation_id,e.id) AND a.person_id=:person))
                ORDER BY starts_at,id""",
                s.params(
                    ctx,
                    person=person["id"],
                    org=person["organization_unit_id"],
                    start=q["starts_at"],
                    end=q["ends_at"],
                ),
            )
            return s.wire(rows)
        if resource == "notifications":
            # Apply current visibility before pagination, so hidden rows cannot truncate a page.
            rows = s.rows(
                c,
                """SELECT n.* FROM gw.notification n WHERE n.workspace_id=:w AND n.generation_id=:g AND n.recipient_id=:person
                AND (n.ref_kind<>'POST' OR EXISTS(SELECT 1 FROM gw.board_post b WHERE (b.workspace_id,b.generation_id,b.id)=(n.workspace_id,n.generation_id,n.ref_id)
                    AND (b.visibility='WORKSPACE' OR b.author_id=:person OR b.audience_org_id=:org)))
                AND (n.ref_kind<>'EVENT' OR EXISTS(SELECT 1 FROM gw.calendar_event e WHERE (e.workspace_id,e.generation_id,e.id)=(n.workspace_id,n.generation_id,n.ref_id)
                    AND (e.owner_id=:person OR (e.scope='DEPARTMENT' AND e.organization_unit_id=:org) OR EXISTS(SELECT 1 FROM gw.event_attendee a
                        WHERE (a.workspace_id,a.generation_id,a.event_id)=(e.workspace_id,e.generation_id,e.id) AND a.person_id=:person))))
                ORDER BY n.id DESC OFFSET :offset LIMIT :limit""",
                s.params(
                    ctx,
                    person=person["id"],
                    org=person["organization_unit_id"],
                    offset=q.get("offset", 0),
                    limit=q.get("limit", 50),
                ),
            )
            return s.wire(rows)
        if resource == "channels":
            rows = s.rows(
                c,
                """SELECT ch.*,m.last_read_seq FROM gw.chat_channel ch JOIN gw.chat_member m
                ON (m.workspace_id,m.generation_id,m.channel_id)=(ch.workspace_id,ch.generation_id,ch.id)
                WHERE ch.workspace_id=:w AND ch.generation_id=:g AND m.person_id=:person AND m.left_at IS NULL ORDER BY ch.id DESC""",
                s.params(ctx, person=person["id"]),
            )
            return s.wire(rows)
        if resource == "messages":
            channel, member = membership(c, ctx, q["id"], person)
            messages = s.rows(
                c,
                """SELECT msg.*,p.name author_name FROM gw.chat_message msg JOIN gw.person p
                ON (p.workspace_id,p.generation_id,p.id)=(msg.workspace_id,msg.generation_id,msg.author_id)
                WHERE msg.workspace_id=:w AND msg.generation_id=:g AND channel_id=:id AND seq>:after ORDER BY seq LIMIT :limit""",
                s.params(
                    ctx, id=q["id"], after=q.get("after", 0), limit=q.get("limit", 100)
                ),
            )
            members = s.rows(
                c,
                """SELECT m.person_id,p.name,m.left_at FROM gw.chat_member m JOIN gw.person p
                ON (p.workspace_id,p.generation_id,p.id)=(m.workspace_id,m.generation_id,m.person_id)
                WHERE m.workspace_id=:w AND m.generation_id=:g AND channel_id=:id ORDER BY m.id""",
                s.params(ctx, id=q["id"]),
            )
            return s.wire(
                {
                    "channel": channel,
                    "messages": messages,
                    "members": members,
                    "last_read_seq": member["last_read_seq"],
                }
            )
        missing()


def mutate(context, resource, id, action, v, key):
    table = {
        "comments": "comment",
        "calendar": "calendar_event",
        "notifications": "notification",
        "channels": "chat_channel",
        "messages": "chat_message",
    }[resource]

    def run(c, ctx):
        p = s.actor(c, ctx, v["acting_person_id"])
        entity = id
        if resource == "comments":
            row = s.one(c, ctx, "comment", id, True) if id else None
            kind = row["target_kind"] if row else v["target_kind"]
            target_id = (
                (row["post_id"] or row["document_id"]) if row else v["target_id"]
            )
            original = target(c, ctx, kind, target_id, p)
            if row:
                s.check_version(row, v)
                s.authored(row, p, "author_id")
                if row["status"] != "ACTIVE":
                    raise s.conflict("IMMUTABLE_DOCUMENT")
                if action == "edit":
                    s.insert(
                        c,
                        ctx,
                        "comment_revision",
                        {
                            "comment_id": id,
                            "revision_no": row["revision_no"],
                            "body": row["body"],
                        },
                    )
                    s.update(
                        c,
                        ctx,
                        "comment",
                        id,
                        {"body": v["body"], "revision_no": row["revision_no"] + 1},
                    )
                else:
                    s.update(
                        c,
                        ctx,
                        "comment",
                        id,
                        {"status": "DELETED", "deleted_at": s.now(c)},
                    )
            else:
                if original["status"] == "DRAFT":
                    raise s.invalid("targetId", "초안에는 댓글을 등록할 수 없습니다.")
                entity = s.insert(
                    c,
                    ctx,
                    "comment",
                    {
                        "target_kind": kind,
                        "post_id": target_id if kind == "POST" else None,
                        "document_id": target_id if kind == "DOCUMENT" else None,
                        "author_id": p["id"],
                        "author_name": p["name"],
                        "body": v["body"],
                    },
                )
                recipient = original["author_id" if kind == "POST" else "drafter_id"]
                if recipient != p["id"] and (
                    kind != "POST"
                    or post_visible(original, s.one(c, ctx, "person", recipient))
                ):
                    notify(
                        c,
                        ctx,
                        [recipient],
                        "COMMENT",
                        kind,
                        target_id,
                        f"C:{entity}:CREATED",
                        original["title"],
                    )
            result = s.one(c, ctx, "comment", entity)
            if result["status"] == "DELETED":
                result["body"] = ""
        elif resource == "calendar":
            row = s.one(c, ctx, "calendar_event", id, True) if id else None
            if row:
                s.authored(row, p, "owner_id")
                s.check_version(row, v)
                if row["status"] != "ACTIVE":
                    raise s.conflict("IMMUTABLE_DOCUMENT")
            if action == "cancel":
                s.update(c, ctx, "calendar_event", id, {"status": "CANCELLED"})
            else:
                if v["ends_at"] <= v["starts_at"]:
                    raise s.invalid("endsAt", "끝은 시작보다 뒤여야 합니다.")
                if v["all_day"]:
                    from zoneinfo import ZoneInfo

                    times = [
                        v[k].astimezone(ZoneInfo("Asia/Seoul"))
                        for k in ("starts_at", "ends_at")
                    ]
                    if any(
                        t.hour or t.minute or t.second or t.microsecond for t in times
                    ):
                        raise s.invalid(
                            "allDay", "종일 일정은 한국 시간 자정부터 자정까지입니다."
                        )
                if len(set(v["attendee_ids"])) != len(v["attendee_ids"]):
                    raise s.invalid("attendeeIds", "참석자가 중복됩니다.")
                org = p["organization_unit_id"] if v["scope"] == "DEPARTMENT" else None
                if v["scope"] == "DEPARTMENT" and (
                    not org or not s.one(c, ctx, "organization_unit", org)["is_active"]
                ):
                    raise s.invalid("scope", "활성 부서 소속 담당자가 필요합니다.")
                values = {
                    k: v[k]
                    for k in [
                        "title",
                        "scope",
                        "starts_at",
                        "ends_at",
                        "all_day",
                        "location",
                    ]
                }
                values["organization_unit_id"] = org
                for a in v["attendee_ids"]:
                    s.actor(c, ctx, a)
                if row:
                    # Existing department scope is frozen across HR moves.
                    if row["scope"] == "DEPARTMENT" and values["scope"] == "DEPARTMENT":
                        values["organization_unit_id"] = row["organization_unit_id"]
                    s.update(c, ctx, table, id, values)
                    c.execute(
                        text(
                            f"DELETE FROM gw.event_attendee WHERE {s.S} AND event_id=:id"
                        ),
                        s.params(ctx, id=id),
                    )
                else:
                    values.update(
                        owner_id=p["id"],
                        event_no=f"GE-{s.number(c, ctx, table, 'id'):06d}",
                    )
                    entity = s.insert(c, ctx, table, values)
                for a in v["attendee_ids"]:
                    s.insert(
                        c, ctx, "event_attendee", {"event_id": entity, "person_id": a}
                    )
            result = calendar_detail(c, ctx, entity, p)
            recipients = [a["person_id"] for a in result["attendees"]]
            if result["scope"] == "DEPARTMENT":
                recipients += [
                    r["id"]
                    for r in s.rows(
                        c,
                        f"SELECT id FROM gw.person WHERE {s.S} AND organization_unit_id=:org",
                        s.params(ctx, org=result["organization_unit_id"]),
                    )
                ]
            notify(
                c,
                ctx,
                recipients,
                "EVENT",
                "EVENT",
                entity,
                f"E:{entity}:V:{result['version']}",
                result["title"],
            )
        elif resource == "notifications":
            row = s.one(c, ctx, table, id, True)
            s.authored(row, p, "recipient_id")
            if row["ref_kind"] == "POST":
                target(c, ctx, "POST", row["ref_id"], p)
            if row["ref_kind"] == "EVENT":
                calendar_detail(c, ctx, row["ref_id"], p)
            c.execute(
                text(
                    f"UPDATE gw.notification SET read_at=coalesce(read_at,clock_timestamp()) WHERE {s.S} AND id=:id"
                ),
                s.params(ctx, id=id),
            )
            result = s.one(c, ctx, table, id)
        elif resource == "channels" and action == "create":
            ids = list(dict.fromkeys([p["id"], *v["member_ids"]]))
            if (v["channel_kind"] == "DIRECT" and len(ids) != 2) or len(ids) < 2:
                raise s.invalid(
                    "memberIds", "대화는 2명 이상, 1:1은 정확히 2명이 필요합니다."
                )
            for a in ids:
                s.actor(c, ctx, a)
            entity = s.insert(
                c,
                ctx,
                table,
                {
                    "code": f"CHAT-{s.number(c, ctx, table, 'id')}",
                    "name": v["name"],
                    "channel_kind": v["channel_kind"],
                    "created_by_id": p["id"],
                },
            )
            for a in ids:
                s.insert(
                    c,
                    ctx,
                    "chat_member",
                    {"channel_id": entity, "person_id": a, "joined_at": s.now(c)},
                )
            result = s.one(c, ctx, table, entity)
        else:
            channel, member = membership(c, ctx, id, p, True)
            if resource == "channels":
                if action == "leave":
                    c.execute(
                        text(
                            f"UPDATE gw.chat_member SET left_at=clock_timestamp() WHERE {s.S} AND id=:member"
                        ),
                        s.params(ctx, member=member["id"]),
                    )
                    result = {"left": True, "id": id}
                else:
                    if v["seq"] > channel["last_seq"]:
                        raise s.invalid(
                            "seq", "아직 없는 메시지는 읽음 처리할 수 없습니다."
                        )
                    c.execute(
                        text(
                            f"UPDATE gw.chat_member SET last_read_seq=greatest(last_read_seq,:seq) WHERE {s.S} AND id=:member"
                        ),
                        s.params(ctx, member=member["id"], seq=v["seq"]),
                    )
                    result = {
                        "id": id,
                        "last_read_seq": max(member["last_read_seq"], v["seq"]),
                    }
            else:
                cached = s.rows(
                    c,
                    f"SELECT * FROM gw.chat_message WHERE {s.S} AND channel_id=:id AND author_id=:person AND client_key=:key",
                    s.params(ctx, id=id, person=p["id"], key=v["client_key"]),
                )
                if cached:
                    if cached[0]["body"] != v["body"]:
                        raise s.invalid("clientKey", "같은 전송 키의 내용이 다릅니다.")
                    entity = cached[0]["id"]
                    result = cached[0]
                else:
                    seq = channel["last_seq"] + 1
                    entity = s.insert(
                        c,
                        ctx,
                        table,
                        {
                            "channel_id": id,
                            "seq": seq,
                            "author_id": p["id"],
                            "body": v["body"],
                            "client_key": v["client_key"],
                        },
                    )
                    c.execute(
                        text(
                            f"UPDATE gw.chat_channel SET last_seq=:seq WHERE {s.S} AND id=:id"
                        ),
                        s.params(ctx, id=id, seq=seq),
                    )
                    result = s.one(c, ctx, table, entity)
        result = s.wire(result)
        s.audit(c, ctx, resource, entity, action, result, table=table)
        return result, "gw." + table, entity

    return s.run_action(
        "gw",
        context,
        f"gw.{resource}.{id or 'new'}.{action}",
        key,
        v,
        run,
        201 if id is None else 200,
    )


def respond(context, id, v, key):
    def run(c, ctx):
        p = s.actor(c, ctx, v["acting_person_id"])
        row = s.one(c, ctx, "calendar_event", id, True)
        s.check_version(row, v)
        if row["status"] != "ACTIVE":
            raise s.conflict("IMMUTABLE_DOCUMENT")
        attendee = s.rows(
            c,
            f"SELECT id FROM gw.event_attendee WHERE {s.S} AND event_id=:id AND person_id=:p",
            s.params(ctx, id=id, p=p["id"]),
        )
        if not attendee:
            missing()
        c.execute(
            text(
                f"UPDATE gw.event_attendee SET response=:response,responded_at=clock_timestamp() WHERE {s.S} AND id=:a"
            ),
            s.params(ctx, a=attendee[0]["id"], response=v["response"]),
        )
        result = s.wire(calendar_detail(c, ctx, id, p))
        s.audit(c, ctx, "calendar", id, "respond", result, table="calendar_event")
        return result, "gw.calendar_event", id

    return s.run_action("gw", context, f"gw.calendar.{id}.respond", key, v, run)
