"""GW-c HR 실제 API, 읽기 경계·스냅샷·원자적 가져오기 검증."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.test_gw import call, ok, why
from tests.test_hr_master import _base, _employee

SEEDS = ()
EMPTY_MODULES = ("gw", "hr")


@pytest.fixture
def org(guest_space):
    c, s, e = guest_space
    ids = _base(c, s)
    employee = _employee(c, s, ids)
    child = ok(
        call(
            c,
            s,
            "POST",
            "/api/v1/hr/departments",
            {"code": "TEAM", "name": "생산팀", "parentId": ids["department"]},
        ),
        201,
    )
    return c, s, e, ids, employee, child


def preview(z):
    return ok(z[0].get("/api/v1/gw/hr-preview"))


def import_people(z, codes=None, digest=None, key=None):
    return call(
        z[0],
        z[1],
        "POST",
        "/import-hr",
        {
            "previewDigest": digest or preview(z)["digest"],
            "employeeCodes": ["E001"] if codes is None else codes,
        },
        key,
    )


def test_hr_import_idempotence_and_local_role_preserved(org):
    c, s, e, *_ = org
    before = preview(org)
    assert before["available"] and before["organizations"] == []
    key = str(uuid4())
    result = ok(import_people(org, digest=before["digest"], key=key))
    assert result["created"] == 1 and result["departments"] == 2
    assert ok(import_people(org, digest=before["digest"], key=key)) == result
    after = preview(org)
    p = after["people"][0]
    assert p["hrEmployeeCode"] == "E001" and p["jobRole"] == "STAFF"
    assert len(after["organizations"]) == 2
    assert (
        next(u for u in after["organizations"] if u["code"] == "TEAM")["parentId"]
        == next(u for u in after["organizations"] if u["code"] == "PROD")["id"]
    )
    ok(
        call(
            c,
            s,
            "PATCH",
            f"/people-master/{p['id']}",
            {
                "expectedVersion": p["version"],
                "jobRole": "EXECUTIVE",
                "isActive": False,
            },
        )
    )
    assert ok(import_people(org))["updated"] == 1
    current = preview(org)["people"][0]
    assert (
        current["id"] == p["id"]
        and current["jobRole"] == "EXECUTIVE"
        and not current["isActive"]
    )
    page = ok(c.get("/api/v1/gw/people"))
    assert (
        page["rows"][0]["organizationName"] == "생산부"
        and page["rows"][0]["hrStatus"] == "ACTIVE"
    )
    with e.connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM hr.employee WHERE workspace_id=:w"),
                {"w": s["workspaceId"]},
            ).scalar_one()
            == 1
        )


def test_collision_rolls_back_all_organization_writes(org):
    c, s, *_ = org
    ok(
        call(
            c,
            s,
            "POST",
            "/people",
            {"code": "E001", "name": "별개 합성 담당자", "jobRole": "STAFF"},
        ),
        201,
    )
    why(import_people(org), "HR_CODE_COLLISION")
    assert preview(org)["organizations"] == []
    assert preview(org)["people"][0]["hrEmployeeCode"] is None


def test_stale_preview_rejected_on_hr_and_gw_change(org):
    c, s, _e, ids, *_ = org
    digest = preview(org)["digest"]
    ok(
        call(
            c,
            s,
            "PATCH",
            f"/api/v1/hr/departments/{ids['department']}",
            {"name": "생산본부"},
        )
    )
    why(import_people(org, digest=digest), "HR_IMPORT_CHANGED")
    digest = preview(org)["digest"]
    ok(
        call(
            c,
            s,
            "POST",
            "/people",
            {"code": "LOCAL", "name": "수동", "jobRole": "STAFF"},
        ),
        201,
    )
    why(import_people(org, digest=digest), "HR_IMPORT_CHANGED")


def test_department_only_and_invalid_selection(org):
    assert ok(import_people(org, codes=[]))["created"] == 0
    assert preview(org)["people"] == []
    assert import_people(org, codes=["E001", "E001"]).status_code == 400
    assert import_people(org, codes=["MISSING"]).status_code == 400


def test_frozen_submission_survives_real_hr_transfer(org):
    c, s, _e, _ids, employee, child = org
    ok(import_people(org))
    p = preview(org)["people"][0]
    approver = ok(
        call(
            c,
            s,
            "POST",
            "/people",
            {"code": "BOSS", "name": "검토자", "jobRole": "MANAGER"},
        ),
        201,
    )
    r = ok(
        call(
            c,
            s,
            "POST",
            "/routes",
            {"code": "ROUTE", "name": "검토", "steps": [{"personId": approver["id"]}]},
        ),
        201,
    )
    doc = ok(
        call(
            c,
            s,
            "POST",
            "/documents",
            {
                "actingPersonId": p["id"],
                "kind": "GENERAL",
                "title": "이동 전 결재",
                "body": "검토",
                "routeId": r["id"],
            },
        ),
        201,
    )
    doc = ok(
        call(
            c,
            s,
            "POST",
            f"/documents/{doc['id']}/submit",
            {"actingPersonId": p["id"], "expectedVersion": doc["version"]},
        )
    )
    assert doc["drafterOrgName"] == "생산부"
    # HR 상태 변경은 HR 발령 API만 이용한다.
    appointment = ok(
        call(
            c,
            s,
            "POST",
            "/api/v1/hr/appointments",
            {
                "employeeId": employee["id"],
                "kind": "TRANSFER",
                "effectiveDate": "2026-03-03",
                "departmentId": child["id"],
            },
        ),
        201,
    )
    ok(call(c, s, "POST", f"/api/v1/hr/appointments/{appointment['id']}/confirm", {}))
    ok(import_people(org))
    assert (
        ok(c.get("/api/v1/gw/people"))["rows"][0 if p["code"] > "BOSS" else 1][
            "organizationName"
        ]
        == "생산팀"
    )
    assert ok(c.get(f"/api/v1/gw/documents/{doc['id']}"))["drafterOrgName"] == "생산부"
    assert (
        call(
            c,
            s,
            "PATCH",
            f"/people/{p['id']}",
            {
                "expectedVersion": next(
                    q for q in preview(org)["people"] if q["id"] == p["id"]
                )["version"],
                "name": "변조",
                "jobRole": "STAFF",
                "isActive": True,
            },
        ).status_code
        == 400
    )


def test_off_keeps_snapshot_and_distinguishes_unavailable(org):
    c, s, _e, *_ = org
    ok(import_people(org))
    digest = preview(org)["digest"]
    response = call(
        c, s, "PATCH", "/api/v1/core/workspace/modules/hr", {"enabled": False}
    )
    assert response.status_code == 200, response.text
    d = preview(org)
    assert (
        not d["available"]
        and d["employees"] is None
        and d["departments"] is None
        and len(d["organizations"]) == 2
    )
    why(import_people(org, digest=digest), "HR_UNAVAILABLE")
    assert ok(c.get("/api/v1/gw/people"))["rows"][0]["hrStatus"] == "UNAVAILABLE"


def test_workspace_isolation_and_csrf(org):
    c, _s, _e, *_ = org
    digest = preview(org)["digest"]
    body = {"previewDigest": digest, "employeeCodes": ["E001"]}
    assert (
        c.post(
            "/api/v1/gw/import-hr", json=body, headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 403
    )
    with TestClient(c.app, base_url="https://testserver") as other:
        other_s = ok(
            other.post(
                "/api/v1/core/guest-sessions",
                json={"nickname": "다른 합성 공간"},
                headers={"Idempotency-Key": str(uuid4())},
            ),
            201,
        )
        d = ok(other.get("/api/v1/gw/hr-preview"))
        assert not d["available"] and d["people"] == [] and d["organizations"] == []
        why(call(other, other_s, "POST", "/import-hr", body), "HR_UNAVAILABLE")


def test_concurrent_import_has_one_winner(org):
    c, s, _e, *_ = org
    digest = preview(org)["digest"]

    def send(_):
        with TestClient(c.app, base_url="https://testserver") as client:
            client.cookies.update(c.cookies)
            return call(
                client,
                s,
                "POST",
                "/import-hr",
                {"previewDigest": digest, "employeeCodes": ["E001"]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(send, range(2)))
    assert sorted(r.status_code for r in replies) == [200, 409]
    assert len(preview(org)["people"]) == 1


@pytest.mark.parametrize(
    "departments",
    [
        [
            {"code": "A", "name": "A", "parentCode": "B", "isActive": True},
            {"code": "B", "name": "B", "parentCode": "A", "isActive": True},
        ],
        [{"code": "A", "name": "A", "parentCode": "X", "isActive": True}],
        [
            {"code": "A", "name": "A", "parentCode": None, "isActive": False},
            {"code": "B", "name": "B", "parentCode": "A", "isActive": True},
        ],
    ],
)
def test_bad_provider_hierarchy_has_no_partial_writes(org, monkeypatch, departments):
    from fs.gw import organization

    monkeypatch.setattr(organization.hr, "departments", lambda c, ctx: departments)
    assert org[0].get("/api/v1/gw/hr-preview").status_code == 400
    with org[2].connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM gw.organization_unit WHERE workspace_id=:w"),
                {"w": org[1]["workspaceId"]},
            ).scalar_one()
            == 0
        )


def test_empty_hr_is_available_not_disabled(guest_space):
    c, _s, _e = guest_space
    data = ok(c.get("/api/v1/gw/hr-preview"))
    assert (
        data["available"]
        and data["employees"] == []
        and data["departments"] == []
        and data["digest"]
    )


def test_retired_status_is_live_and_does_not_disable_current_gw_role(org):
    c, s, _e, _ids, employee, _child = org
    ok(import_people(org))
    appointment = ok(
        call(
            c,
            s,
            "POST",
            "/api/v1/hr/appointments",
            {
                "employeeId": employee["id"],
                "kind": "RETIRE",
                "effectiveDate": "2026-09-01",
            },
        ),
        201,
    )
    ok(call(c, s, "POST", f"/api/v1/hr/appointments/{appointment['id']}/confirm", {}))
    person = ok(c.get("/api/v1/gw/people"))["rows"][0]
    assert person["hrStatus"] == "RETIRED" and person["isActive"]
    assert import_people(org).status_code == 400
    assert ok(import_people(org, codes=[]))["updated"] == 0


def test_non_gw_hr_code_keeps_source_identity_and_does_not_duplicate(org):
    c, s, _e, ids, *_ = org
    _employee(c, s, ids, code="E_UNDERSCORE")
    ok(import_people(org, codes=["E_UNDERSCORE"]))
    p = preview(org)["people"][0]
    assert p["code"].startswith("HR-") and p["hrEmployeeCode"] == "E_UNDERSCORE"
    assert ok(import_people(org, codes=["E_UNDERSCORE"]))["updated"] == 1
    assert preview(org)["people"][0]["id"] == p["id"]


def test_approval_step_organization_frozen_after_hr_department_rename(org):
    c, s, _e, ids, *_ = org
    ok(import_people(org))
    reviewer = preview(org)["people"][0]
    drafter = ok(
        call(
            c,
            s,
            "POST",
            "/people",
            {"code": "DRAFT", "name": "합성 기안자", "jobRole": "STAFF"},
        ),
        201,
    )
    route = ok(
        call(
            c,
            s,
            "POST",
            "/routes",
            {
                "code": "REVIEW",
                "name": "HR 담당자 검토",
                "steps": [{"personId": reviewer["id"]}],
            },
        ),
        201,
    )
    doc = ok(
        call(
            c,
            s,
            "POST",
            "/documents",
            {
                "actingPersonId": drafter["id"],
                "kind": "GENERAL",
                "title": "조직 기록",
                "body": "합성 기안",
                "routeId": route["id"],
            },
        ),
        201,
    )
    doc = ok(
        call(
            c,
            s,
            "POST",
            f"/documents/{doc['id']}/submit",
            {"actingPersonId": drafter["id"], "expectedVersion": doc["version"]},
        )
    )
    assert doc["steps"][0]["organizationName"] == "생산부"
    ok(
        call(
            c,
            s,
            "PATCH",
            f"/api/v1/hr/departments/{ids['department']}",
            {"name": "새 생산본부"},
        )
    )
    ok(import_people(org))
    current = next(
        p for p in ok(c.get("/api/v1/gw/people"))["rows"] if p["id"] == reviewer["id"]
    )
    assert current["organizationName"] == "새 생산본부"
    doc = ok(c.get(f"/api/v1/gw/documents/{doc['id']}"))
    assert doc["steps"][0]["organizationName"] == "생산부"
    doc = ok(
        call(
            c,
            s,
            "POST",
            f"/documents/{doc['id']}/approve",
            {"actingPersonId": reviewer["id"], "expectedVersion": doc["version"]},
        )
    )
    assert (
        doc["status"] == "APPROVED" and doc["steps"][0]["organizationName"] == "생산부"
    )


def test_role_options_include_more_than_one_page(org):
    c, s, engine, *_ = org
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO gw.person(workspace_id,generation_id,code,name,job_role) SELECT :w,:g,'S-'||lpad(n::text,3,'0'),'합성 담당자 '||n,'STAFF' FROM generate_series(1,101) n"
            ),
            {"w": s["workspaceId"], "g": s["generationId"]},
        )
    assert len(ok(c.get("/api/v1/gw/people-options"))) == 101
    page = ok(c.get("/api/v1/gw/people?limit=100"))
    assert page["total"] == 101 and len(page["rows"]) == 100


def test_people_master_partial_update_is_versioned_and_scoped(org):
    c, s, *_ = org
    ok(import_people(org))
    p = preview(org)["people"][0]
    why(
        call(
            c,
            s,
            "PATCH",
            f"/people-master/{p['id']}",
            {"expectedVersion": p["version"] - 1 or 999, "jobRole": "MANAGER"},
        ),
        "VERSION_CONFLICT",
    )
    assert (
        call(
            c,
            s,
            "PATCH",
            f"/people-master/{p['id']}",
            {"expectedVersion": p["version"], "name": None},
        ).status_code
        == 400
    )
    assert (
        call(
            c,
            s,
            "PATCH",
            f"/people-master/{int(p['id']) + 100000}",
            {"expectedVersion": 1, "jobRole": "MANAGER"},
        ).status_code
        == 404
    )
    assert ok(c.get("/api/v1/gw/people-master?search=E001"))[0]["id"] == p["id"]
