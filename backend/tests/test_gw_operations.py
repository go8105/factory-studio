"""Operating policy integration: role, fresh auth, scope, CAS and immutable history."""

# ruff: noqa: F401, F811
from uuid import uuid4

from sqlalchemy import text
from test_gw_company import context
from test_gw_company_work import api, connect_staff, initialize
from test_hr_work import company_env


def test_operating_policy_requires_current_role_fresh_auth_and_version(company_env):
    engine, co, admin, staff = company_env
    person = initialize(company_env)
    connect_staff(company_env)
    initial = api(admin, co, "operations", method="GET")
    assert initial.status_code == 200
    assert initial.json()["data"]["ready"] is False
    body = {
        "expectedVersion": 0,
        "policy": {"responsiblePersonId": str(person), "reason": "합성 최초 운영 기준"},
    }
    denied = api(admin, co, "operating-policies", body)
    assert (
        denied.status_code == 403
        and denied.json()["error"]["code"] == "STEP_UP_REQUIRED"
    )
    # The authentication engine has its own full real MFA tests. Here set a synthetic
    # current assurance in the isolated DB to concentrate on GW authorization/CAS.
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET assurance='MFA',verified_at=clock_timestamp() WHERE user_id=:u AND revoked_at IS NULL"
            ),
            {"u": context(engine, admin).user_id},
        )
    key = str(uuid4())
    first = api(admin, co, "operating-policies", body, key=key)
    assert first.status_code == 200, first.text
    assert api(admin, co, "operating-policies", body, key=key).json() == first.json()
    assert api(admin, co, "operating-policies", body).status_code == 409
    assert api(staff, co, "operating-policies", body).status_code == 403
    bad = {
        "expectedVersion": 1,
        "policy": body["policy"] | {"backupIntervalMinutes": 60},
    }
    assert api(admin, co, "operating-policies", bad).status_code == 400
    second = api(
        admin,
        co,
        "operating-policies",
        {
            "expectedVersion": 1,
            "policy": body["policy"]
            | {"rpoMinutes": 90, "reason": "합성 손실 목표 검토"},
        },
    )
    assert second.status_code == 200, second.text
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM gw.operating_policy_revision WHERE workspace_id=:w"
                ),
                {"w": co["companyId"]},
            ).scalar_one()
            == 2
        )
        assert (
            c.execute(
                text(
                    "SELECT rpo_minutes FROM gw.operating_policy_revision WHERE workspace_id=:w AND revision_no=1"
                ),
                {"w": co["companyId"]},
            ).scalar_one()
            == 60
        )
    latest = api(admin, co, "operations", method="GET").json()["data"]
    assert (
        latest["version"] == 2
        and latest["revisionNo"] == 2
        and latest["ready"] is False
    )
    assert latest["blockers"]
    assert (
        api(staff, co, "operations", method="GET").json()["data"]["administrator"]
        is False
    )
