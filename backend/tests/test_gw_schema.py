"""FS-030a database constraints only; approval service remains FS-030b."""

from datetime import date

import pytest
from seed.copy import copy_template_generation
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

SEEDS = ("erp",)
EMPTY_MODULES = ("gw",)


@pytest.fixture
def gw_db(guest_space):
    _, data, engine = guest_space
    with engine.connect() as c:
        tx = c.begin()
        s = {"w": data["workspaceId"], "g": data["generationId"]}
        s["person"] = c.execute(
            text(
                "INSERT INTO gw.person(workspace_id,generation_id,code,name,job_role) VALUES (:w,:g,'TEST','합성 담당자','STAFF') RETURNING id"
            ),
            s,
        ).scalar_one()
        s["route"] = c.execute(
            text(
                "INSERT INTO gw.approval_route(workspace_id,generation_id,code,name) VALUES (:w,:g,'TEST','합성 결재선') RETURNING id"
            ),
            s,
        ).scalar_one()
        yield c, s
        tx.rollback()


def document(c, s, serial=1):
    return c.execute(
        text(
            "INSERT INTO gw.approval_document(workspace_id,generation_id,serial,document_no,kind,title,body,drafter_id,drafter_code,drafter_name,drafter_job_role,route_id,route_code,route_name) VALUES (:w,:g,:serial,:number,'GENERAL','검증 기안','검증 내용',:person,'TEST','합성 담당자','STAFF',:route,'TEST','합성 결재선') RETURNING id"
        ),
        {**s, "serial": serial, "number": f"GW-{serial:06d}"},
    ).scalar_one()


def rejected(c, sql, s):
    with pytest.raises(IntegrityError), c.begin_nested():
        c.execute(text(sql), s)


def test_stage_range_and_duplicate_person(gw_db):
    c, s = gw_db
    sql = "INSERT INTO gw.route_step(workspace_id,generation_id,route_id,seq,person_id) VALUES (:w,:g,:route,:seq,:person)"
    for seq in (0, 4):
        rejected(c, sql, {**s, "seq": seq})
    c.execute(text(sql), {**s, "seq": 1})
    rejected(c, sql, {**s, "seq": 2})
    rejected(c, "DELETE FROM gw.person WHERE id=:person", s)


def test_scope_reference_and_document_state(gw_db):
    c, s = gw_db
    s["doc"] = document(c, s)
    rejected(c, "UPDATE gw.approval_document SET status='IN_REVIEW' WHERE id=:doc", s)
    rejected(
        c, "UPDATE gw.approval_document SET amount=1,currency=NULL WHERE id=:doc", s
    )
    rejected(
        c, "UPDATE gw.approval_document SET previous_document_id=id WHERE id=:doc", s
    )
    # Valid other generation anchor, but foreign person/route remain in original generation.
    other = c.execute(
        text(
            "INSERT INTO core.data_generation(workspace_id,seed_version,seed_date,status) SELECT workspace_id,seed_version,seed_date,'preparing' FROM core.data_generation WHERE id=:g RETURNING id"
        ),
        s,
    ).scalar_one()
    rejected(
        c,
        "UPDATE gw.approval_document SET generation_id=:other WHERE id=:doc",
        {**s, "other": other},
    )


def test_source_claim_and_snapshot_checks(gw_db):
    c, s = gw_db
    s["doc"] = document(c, s)
    other = document(c, s, 2)
    sql = "UPDATE gw.approval_document SET kind='ERP_PURCHASE',source_kind='PURCHASE_INVOICE',source_no='PI-TEST',source_snapshot=CAST(:snapshot AS jsonb),source_digest=:digest,source_status='draft' WHERE id=:doc"
    rejected(c, sql, {**s, "snapshot": "[]", "digest": "a" * 64})
    rejected(c, sql, {**s, "snapshot": "{}", "digest": "broken"})
    c.execute(text(sql), {**s, "snapshot": "{}", "digest": "a" * 64})
    c.execute(text(sql), {**s, "doc": other, "snapshot": "{}", "digest": "a" * 64})
    submit = "UPDATE gw.approval_document SET status='IN_REVIEW',submitted_at=clock_timestamp(),submission_order=:ord,current_step=1 WHERE id=:doc"
    c.execute(text(submit), {**s, "ord": 1})
    rejected(c, submit, {**s, "doc": other, "ord": 2})
    c.execute(
        text(
            "UPDATE gw.approval_document SET status='REJECTED',closed_at=clock_timestamp(),current_step=NULL WHERE id=:doc"
        ),
        s,
    )
    c.execute(text(submit), {**s, "doc": other, "ord": 2})


def test_decision_fields_and_event_uniqueness(gw_db):
    c, s = gw_db
    s["doc"] = document(c, s)
    c.execute(
        text(
            "INSERT INTO gw.approval_step(workspace_id,generation_id,document_id,seq,person_id,person_code,person_name,person_job_role) VALUES (:w,:g,:doc,1,:person,'TEST','합성 담당자','STAFF')"
        ),
        s,
    )
    rejected(
        c,
        "UPDATE gw.approval_step SET status='REJECTED',decided_at=clock_timestamp() WHERE document_id=:doc",
        s,
    )
    c.execute(
        text(
            "UPDATE gw.approval_step SET status='REJECTED',decision_reason='보완 필요',decided_at=clock_timestamp() WHERE document_id=:doc"
        ),
        s,
    )
    sql = "INSERT INTO gw.approval_event(workspace_id,generation_id,document_id,event_seq,event_type,acting_person_id,person_code,person_name,person_job_role,actor_kind,actor_key,document_version,step_seq,reason) VALUES (:w,:g,:doc,1,'REJECTED',:person,'TEST','합성 담당자','STAFF','SEED','seed',1,:step,:reason)"
    rejected(c, sql, {**s, "step": None, "reason": "보완 필요"})
    rejected(c, sql, {**s, "step": 1, "reason": None})
    c.execute(text(sql), {**s, "step": 1, "reason": "보완 필요"})
    rejected(c, sql, {**s, "step": 1, "reason": "보완 필요"})


def test_post_lifecycle_and_successor_unique(gw_db):
    c, s = gw_db
    sql = "INSERT INTO gw.board_post(workspace_id,generation_id,serial,post_no,board_kind,author_id,author_code,author_name,author_job_role,title,body,previous_post_id) VALUES (:w,:g,:serial,:number,'FREE',:person,'TEST','합성 담당자','STAFF','게시글','본문',:previous) RETURNING id"
    s["post"] = c.execute(
        text(sql), {**s, "serial": 1, "number": "GB-1", "previous": None}
    ).scalar_one()
    rejected(c, "UPDATE gw.board_post SET status='WITHDRAWN' WHERE id=:post", s)
    c.execute(
        text(
            "UPDATE gw.board_post SET status='PUBLISHED',published_at=clock_timestamp() WHERE id=:post"
        ),
        s,
    )
    c.execute(text(sql), {**s, "serial": 2, "number": "GB-2", "previous": s["post"]})
    rejected(c, sql, {**s, "serial": 3, "number": "GB-3", "previous": s["post"]})


def test_copy_remaps_internal_links_and_keeps_semantic_digest(gw_db):
    c, s = gw_db
    s["doc"] = document(c, s)
    successor = document(c, s, 2)
    c.execute(
        text(
            "UPDATE gw.approval_document SET previous_document_id=:doc,round_no=2 WHERE id=:successor"
        ),
        {**s, "successor": successor},
    )
    c.execute(
        text(
            "UPDATE gw.approval_document SET kind='ERP_PURCHASE',source_kind='PURCHASE_INVOICE',source_no='PI-TEST',source_snapshot=CAST(:snap AS jsonb),source_digest=:digest,source_status='draft' WHERE id=:doc"
        ),
        {
            **s,
            "snap": '{"display":{"invoiceDate":"2026-09-24","dueDate":null,"confirmedAt":null,"cancelledAt":null}}',
            "digest": "a" * 64,
        },
    )
    new, _, _ = copy_template_generation(c, s["w"], s["g"], s["w"], date(2026, 9, 25))
    rows = (
        c.execute(
            text(
                "SELECT id,previous_document_id,drafter_id,source_digest,source_snapshot FROM gw.approval_document WHERE workspace_id=:w AND generation_id=:g ORDER BY serial"
            ),
            {**s, "g": new},
        )
        .mappings()
        .all()
    )
    assert len(rows) == 2 and rows[1]["previous_document_id"] == rows[0]["id"]
    assert rows[0]["drafter_id"] != s["person"]
    assert rows[0]["source_digest"] == "a" * 64
    assert rows[0]["source_snapshot"]["display"]["invoiceDate"] == "2026-09-25"
