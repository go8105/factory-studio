"""회사 협업: 동일 회사 TX, 현재 주체/부모 ACL을 영수증보다 먼저 확인한다."""

from fs.gw import collaboration as collab
from fs.gw import company
from fs.gw import company_identity as identities
from fs.gw import company_work as work
from fs.gw import service as s


def notification_filter():
    doc = work.acl("documents", "d")
    post = work.acl("posts", "d")
    return f"""((n.ref_kind='DOCUMENT' AND EXISTS(SELECT 1 FROM gw.approval_document d WHERE (d.workspace_id,d.generation_id,d.id)=(n.workspace_id,n.generation_id,n.ref_id) AND {doc}))
       OR (n.ref_kind='POST' AND EXISTS(SELECT 1 FROM gw.board_post d WHERE (d.workspace_id,d.generation_id,d.id)=(n.workspace_id,n.generation_id,n.ref_id) AND {post}))
       OR (n.ref_kind='EVENT' AND EXISTS(SELECT 1 FROM gw.calendar_event e WHERE (e.workspace_id,e.generation_id,e.id)=(n.workspace_id,n.generation_id,n.ref_id) AND (e.owner_id=:person OR (e.scope='DEPARTMENT' AND e.organization_unit_id=:org) OR EXISTS(SELECT 1 FROM gw.event_attendee a WHERE (a.workspace_id,a.generation_id,a.event_id)=(e.workspace_id,e.generation_id,e.id) AND a.person_id=:person)))))"""


def notification_target(c, ctx, row, p):
    if row["recipient_id"] != p["id"]:
        work.not_found()
    if row["ref_kind"] in {"POST", "DOCUMENT"}:
        collab.target(c, ctx, row["ref_kind"], row["ref_id"], p, company_mode=True)
    elif row["ref_kind"] == "EVENT":
        collab.calendar_detail(c, ctx, row["ref_id"], p)
    else:
        work.not_found()


def query(context, company_id, resource, **q):
    with company.transaction(context, company_id) as (c, ctx, _):
        identity, _ = company.principal(c, ctx)
        p = s.one(c, ctx, "person", identity["id"])
        if resource == "notifications":
            return s.wire(
                s.rows(
                    c,
                    f"SELECT n.* FROM gw.notification n WHERE n.workspace_id=:w AND n.generation_id=:g AND n.recipient_id=:person AND {notification_filter()} ORDER BY n.id DESC LIMIT :limit OFFSET :offset",
                    s.params(
                        ctx,
                        person=p["id"],
                        org=p["organization_unit_id"],
                        active=sorted(identities.active_people(c, ctx)),
                        limit=q.get("limit", 50),
                        offset=q.get("offset", 0),
                    ),
                )
            )
        return collab.query_scoped(c, ctx, resource, p["id"], company_mode=True, **q)


def mutate(context, company_id, resource, id, operation, values, key):
    def authorize(c, ctx, identity):
        p = s.one(c, ctx, "person", identity["id"])
        v = {**values, "acting_person_id": p["id"]}
        collab.authorize_scoped(c, ctx, resource, id, operation, v, company_mode=True)
        if (
            resource == "comments"
            and id
            and s.one(c, ctx, "comment", id)["author_id"] != p["id"]
        ):
            work.not_found()
        if resource == "calendar" and id:
            row = s.one(c, ctx, "calendar_event", id)
            if operation == "respond":
                if not s.rows(
                    c,
                    f"SELECT 1 FROM gw.event_attendee WHERE {s.S} AND event_id=:id AND person_id=:person",
                    s.params(ctx, id=id, person=p["id"]),
                ):
                    work.not_found()
            elif row["owner_id"] != p["id"]:
                work.not_found()
        if resource == "notifications":
            notification_target(c, ctx, s.one(c, ctx, "notification", id), p)

    def run(c, ctx, identity):
        for participant in values.get("attendee_ids", values.get("member_ids", [])):
            identities.require_active(c, ctx, participant)
        v = {**values, "acting_person_id": identity["id"]}
        if resource == "calendar" and operation == "respond":
            return collab.respond_scoped(c, ctx, id, v)
        return collab.mutate_scoped(
            c, ctx, resource, id, operation, v, company_mode=True
        )

    return company.action(
        context,
        company_id,
        f"company.{resource}.{id}.{operation}",
        key,
        values,
        run,
        authorize=authorize,
    )
