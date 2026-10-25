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
    assert all(
        check["state"] == "CONFIG_REQUIRED"
        for check in initial.json()["data"]["evidenceChecks"]
    )
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
    assert latest["launchGate"]["ready"] is False
    assert latest["launchGate"]["unverifiedCount"] == 4
    assert len(latest["launchGate"]["checks"]) == 12
    assert (
        api(staff, co, "operations", method="GET").json()["data"]["administrator"]
        is False
    )


def test_launch_condition_rechecks_responsible_staff_connection(
    company_env, monkeypatch
):
    from test_gw_evidence import prepare

    prepare(company_env, monkeypatch)
    engine, co, admin, _staff = company_env
    with engine.connect() as c:
        binding = (
            c.execute(
                text(
                    "SELECT b.id,b.version,b.person_id FROM gw.person_identity_binding b JOIN hr.work_account a ON a.user_id=b.user_id AND a.workspace_id=b.workspace_id WHERE b.workspace_id=:w AND a.work_role='STAFF'"
                ),
                {"w": co["companyId"]},
            )
            .mappings()
            .one()
        )
    current = api(admin, co, "operations", method="GET").json()["data"]
    policy = current["policy"] | {
        "responsiblePersonId": str(binding["person_id"]),
        "expectedPeople": 2,
        "reason": "합성 담당자 연결 점검",
    }
    assert (
        api(
            admin, co, "operating-policies", {"expectedVersion": 1, "policy": policy}
        ).status_code
        == 200
    )

    def responsible_state():
        data = api(admin, co, "operations", method="GET").json()["data"]
        assert not data["ready"]
        return next(
            c["state"]
            for c in data["launchGate"]["checks"]
            if c["code"] == "RESPONSIBLE"
        )

    assert responsible_state() == "CONFIRMED"
    assert (
        api(
            admin,
            co,
            f"identity-bindings/{binding['id']}/suspend",
            {"expectedVersion": binding["version"], "reason": "합성 담당자 연결 회수"},
        ).status_code
        == 200
    )
    assert responsible_state() == "BLOCKED"


def test_configuration_guidance_is_scoped_to_current_company_roles(
    company_env, monkeypatch
):
    from fs.gw import operating_evidence
    from fs.gw.trust_configuration import ISSUES, TrustConfigurationError, guidance

    engine, co, admin, staff = company_env
    person = initialize(company_env)
    connect_staff(company_env)
    for code in ISSUES:

        def unavailable(code=code):
            raise TrustConfigurationError(code)

        monkeypatch.setattr(operating_evidence, "from_environment", unavailable)
        current = api(admin, co, "operations", method="GET").json()["data"]
        assert current["configurationIssue"] == guidance(code)
        assert current["canEdit"] and not current["ready"]
        assert current["launchGate"]["unverifiedCount"] == 4
        assert all(c["state"] == "CONFIG_REQUIRED" for c in current["evidenceChecks"])
        employee = api(staff, co, "operations", method="GET").json()["data"]
        assert not employee["administrator"] and "configurationIssue" not in employee
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.role_grant SET is_active=false WHERE workspace_id=:w AND person_id=:p"
            ),
            {"w": co["companyId"], "p": person},
        )
        c.execute(
            text(
                "UPDATE gw.role_grant SET role_key='AUDITOR',is_active=true WHERE workspace_id=:w AND person_id=:p AND role_key='SECURITY_ADMIN'"
            ),
            {"w": co["companyId"], "p": person},
        )
    auditor = api(admin, co, "operations", method="GET").json()["data"]
    assert auditor["administrator"] and not auditor["canEdit"]
    assert auditor["configurationIssue"] == guidance(code)
