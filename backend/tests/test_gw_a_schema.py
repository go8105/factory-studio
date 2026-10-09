"""GW-a 실제 PostgreSQL: 복합 범위·병렬 UK·재전송·조직 self-FK 복사/정리."""

from datetime import date
from uuid import uuid4

import pytest
from seed.copy import copy_template
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

SEEDS = ()
EMPTY_MODULES = ("gw",)


def context(connection, session):
    w = session["workspaceId"]
    g = connection.execute(
        text("SELECT active_generation_id FROM core.workspace WHERE id=:w"), {"w": w}
    ).scalar_one()
    for code in ("TEST1", "TEST2"):
        connection.execute(
            text(
                "INSERT INTO gw.person(workspace_id,generation_id,code,name,job_role) VALUES(:w,:g,:code,'합성 담당자','STAFF')"
            ),
            {"w": w, "g": g, "code": code},
        )
    people = (
        connection.execute(
            text("SELECT id FROM gw.person WHERE workspace_id=:w ORDER BY id"), {"w": w}
        )
        .scalars()
        .all()
    )
    return {"w": w, "g": g}, people


def test_parallel_stage_still_rejects_duplicate_person(guest_space):
    _, session, engine = guest_space
    with engine.begin() as c:
        p, people = context(c, session)
        p["r"] = c.execute(
            text(
                "INSERT INTO gw.approval_route(workspace_id,generation_id,code,name) VALUES(:w,:g,'PARALLEL','병렬 시험') RETURNING id"
            ),
            p,
        ).scalar_one()
        for person in people[:2]:
            c.execute(
                text(
                    "INSERT INTO gw.route_step(workspace_id,generation_id,route_id,seq,person_id) VALUES(:w,:g,:r,1,:person)"
                ),
                {**p, "person": person},
            )
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(
                text(
                    "INSERT INTO gw.route_step(workspace_id,generation_id,route_id,seq,person_id) VALUES(:w,:g,:r,2,:person)"
                ),
                {**p, "person": people[0]},
            )


def test_scope_and_notification_retry_key(guest_space):
    _, session, engine = guest_space
    with engine.begin() as c:
        p, people = context(c, session)
        q = {**p, "person": people[0]}
        sql = text(
            "INSERT INTO gw.notification(workspace_id,generation_id,recipient_id,kind,ref_kind,ref_id,event_key,title) VALUES(:w,:g,:person,'NOTICE','POST',1,'event-one','합성 알림')"
        )
        c.execute(sql, q)
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(sql, q)
        other_w, other_g, _, _ = copy_template(
            c, p["w"], p["g"], date(2026, 9, 24), str(uuid4()), schemas=()
        )
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(sql, {**q, "w": other_w, "g": other_g})


def test_populated_org_parent_and_person_copy(guest_space):
    _, session, engine = guest_space
    with engine.begin() as c:
        p, people = context(c, session)
        parent = c.execute(
            text(
                "INSERT INTO gw.organization_unit(workspace_id,generation_id,code,name) VALUES(:w,:g,'ROOT','합성 본부') RETURNING id"
            ),
            p,
        ).scalar_one()
        child = c.execute(
            text(
                "INSERT INTO gw.organization_unit(workspace_id,generation_id,code,name,parent_id) VALUES(:w,:g,'CHILD','합성 부서',:parent) RETURNING id"
            ),
            {**p, "parent": parent},
        ).scalar_one()
        c.execute(
            text("UPDATE gw.person SET organization_unit_id=:child WHERE id=:person"),
            {"child": child, "person": people[0]},
        )
        w, g, counts, _ = copy_template(
            c, p["w"], p["g"], date(2026, 9, 25), str(uuid4()), schemas=("gw",)
        )
        assert counts["gw.organization_unit"] == 2
        rows = (
            c.execute(
                text(
                    "SELECT code,id,parent_id FROM gw.organization_unit WHERE workspace_id=:w AND generation_id=:g"
                ),
                {"w": w, "g": g},
            )
            .mappings()
            .all()
        )
        copied = {r["code"]: r for r in rows}
        assert copied["CHILD"]["parent_id"] == copied["ROOT"]["id"] != parent
        assert (
            c.execute(
                text(
                    "SELECT organization_unit_id FROM gw.person WHERE workspace_id=:w AND code=(SELECT code FROM gw.person WHERE id=:old)"
                ),
                {"w": w, "old": people[0]},
            ).scalar_one()
            == copied["CHILD"]["id"]
        )
    # guest_space 정리에서 실제 populated self-FK 및 person → org 참조를 삭제한다.
