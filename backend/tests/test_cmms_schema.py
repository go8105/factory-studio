"""FS-029a CMMS DB 제약만 검사한다(AC-185·187·188·190·191 중 DB가 강제하는 부분). 서비스·API는 FS-029b."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def cmms_db(guest_space):
    _, data, engine = guest_space
    with engine.connect() as c:
        tx = c.begin()
        s = {"w": data["workspaceId"], "g": data["generationId"]}
        s["asset"] = c.execute(
            text(
                "INSERT INTO cmms.asset(workspace_id,generation_id,code,name,asset_type,source,source_code) "
                "VALUES (:w,:g,'INJ-02','사출기 2','INJECTION','MES','INJ-02') RETURNING id"
            ),
            s,
        ).scalar_one()
        s["plan"] = c.execute(
            text(
                "INSERT INTO cmms.pm_plan(workspace_id,generation_id,asset_id,code,title,checklist,interval_days,start_on) "
                "VALUES (:w,:g,:asset,'PM-INJ-02','주간 점검','냉각수·윤활',7,'2026-09-01') RETURNING id"
            ),
            s,
        ).scalar_one()
        yield c, s
        tx.rollback()


def rejected(c, sql, s):
    with pytest.raises(IntegrityError), c.begin_nested():
        c.execute(text(sql), s)


BM = (
    "INSERT INTO cmms.work_order(workspace_id,generation_id,wo_no,asset_id,kind,source,source_ref,title,"
    "requested_at,failure_at) VALUES (:w,:g,:no,:asset,'BM',:source,:ref,'점검',now(),now()) RETURNING id"
)


def test_imported_asset_is_unique_per_source_code(cmms_db):
    """AC-185: 같은 원천 코드는 1건, CMMS 직접 등록은 원천 코드가 없다."""
    c, s = cmms_db
    rejected(
        c,
        "INSERT INTO cmms.asset(workspace_id,generation_id,code,name,asset_type,source,source_code) "
        "VALUES (:w,:g,'INJ-02B','중복','INJECTION','MES','INJ-02')",
        s,
    )
    rejected(
        c,
        "INSERT INTO cmms.asset(workspace_id,generation_id,code,name,asset_type,source,source_code) "
        "VALUES (:w,:g,'UT-AIR','압축기','UTILITY','CMMS','X')",
        s,
    )
    c.execute(
        text(
            "INSERT INTO cmms.asset(workspace_id,generation_id,code,name,asset_type,source) "
            "VALUES (:w,:g,'UT-AIR','공용 압축기','UTILITY','CMMS')"
        ),
        s,
    )


def test_one_live_work_order_per_signal(cmms_db):
    """AC-188: 같은 신호는 취소되지 않은 작업지시 1건, 취소하면 다시 전환할 수 있다."""
    c, s = cmms_db
    first = c.execute(
        text(BM), {**s, "no": "WO-1", "source": "SPC_SIGNAL", "ref": "spc:41"}
    ).scalar_one()
    rejected(c, BM, {**s, "no": "WO-2", "source": "SPC_SIGNAL", "ref": "spc:41"})
    c.execute(
        text(
            "UPDATE cmms.work_order SET status='CANCELLED', cancelled_at=now(), cancel_reason='중복 접수' WHERE id=:id"
        ),
        {"id": first},
    )
    c.execute(text(BM), {**s, "no": "WO-3", "source": "SPC_SIGNAL", "ref": "spc:41"})
    rejected(c, BM, {**s, "no": "WO-4", "source": "MANUAL", "ref": "x"})


def test_one_pm_work_order_per_plan_due_date(cmms_db):
    """AC-187"""
    c, s = cmms_db
    pm = (
        "INSERT INTO cmms.work_order(workspace_id,generation_id,wo_no,asset_id,kind,source,pm_plan_id,due_on,title,"
        "requested_at) VALUES (:w,:g,:no,:asset,'PM','PM_PLAN',:plan,'2026-09-08','주간 점검',now())"
    )
    c.execute(text(pm), {**s, "no": "WO-P1"})
    rejected(c, pm, {**s, "no": "WO-P2"})


def test_status_requires_times_and_completion_fields(cmms_db):
    """AC-190·191: 상태별 시각·필수 칸, BM 완료는 복구 시각(정지 시작 이후)."""
    c, s = cmms_db
    wo = c.execute(
        text(BM), {**s, "no": "WO-9", "source": "MANUAL", "ref": None}
    ).scalar_one()
    p = {"id": wo}
    rejected(c, "UPDATE cmms.work_order SET status='IN_PROGRESS' WHERE id=:id", p)
    c.execute(
        text(
            "UPDATE cmms.work_order SET status='IN_PROGRESS', started_at=requested_at WHERE id=:id"
        ),
        p,
    )
    rejected(
        c,
        "UPDATE cmms.work_order SET status='COMPLETED', completed_at=now(), cause_category='WEAR', action='교체' WHERE id=:id",
        p,
    )
    rejected(
        c,
        "UPDATE cmms.work_order SET status='COMPLETED', completed_at=now(), cause_category='WEAR', action='교체', "
        "restored_at=failure_at - interval '1 hour' WHERE id=:id",
        p,
    )
    c.execute(
        text(
            "UPDATE cmms.work_order SET status='COMPLETED', completed_at=now(), cause_category='WEAR', action='호스 교체', "
            "restored_at=failure_at + interval '2 hours' WHERE id=:id"
        ),
        p,
    )
    rejected(
        c,
        "INSERT INTO cmms.part_usage(workspace_id,generation_id,work_order_id,spare_part_id,qty,used_at) "
        "VALUES (:w,:g,:id,:id,0,now())",
        {**s, **p},
    )


def test_guest_has_cmms_module(guest_space):
    client, _, _ = guest_space
    modules = {
        m["moduleKey"]: m["enabled"]
        for m in client.get("/api/v1/core/workspace/modules").json()["data"]
    }
    assert modules["cmms"] is True
