"""Synthetic PostgreSQL security/HR flows with the private journal enabled."""

# ruff: noqa: F811
import json
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_gw_emergency import emergency_env  # noqa: F401
from test_gw_emergency import (
    test_kit_once_response_replaces_previous_and_no_credentials_in_audit as kit_flow,
)
from test_gw_security_transactions import enroll, identity  # noqa: F401
from test_gw_security_transactions import (
    test_recent_auth_rotation_and_other_session_revocation as rotation_flow,
)
from test_gw_security_transactions import (
    test_recovery_code_race_restricts_session_and_reenrollment as recovery_flow,
)
from test_hr_users import manage, users
from test_hr_users import (
    test_admin_creates_account_once_and_hides_credentials as create_flow,
)
from test_hr_users import (
    test_platform_company_creation_atomic_and_company_admin_not_global as company_flow,
)
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401

from fs.common.errors import ApiError
from fs.core.security import service
from fs.core.security.journal import verified_records, verify
from fs.gw.security_journal import confirm_records


def records_for(journal):
    directory, key = journal
    state = verify(directory, key)
    return verified_records(directory, key, state["head"])[1]


def checked(engine, journal):
    records = records_for(journal)
    with engine.connect() as c:
        result = confirm_records(c, records)
    assert result["commitsConfirmed"] and not result["completenessConfirmed"]
    return records


def test_enrollment_records_exclude_all_credentials(identity, journal):
    engine, ctx, password, _ = identity
    started, confirmed = enroll(identity)
    records = checked(engine, journal)
    operations = {r["payload"]["operation"] for r in records}
    assert {
        "security.mfa.enrollment.started",
        "security.mfa.enrolled",
        "security.throttle.changed",
    } <= operations
    serialized = json.dumps(records)
    secrets_absent = all(
        value not in serialized
        for value in [
            password,
            ctx.token,
            started["setupKey"],
            *confirmed["recoveryCodes"],
        ]
    )
    assert secrets_absent
    fields_absent = all(
        name not in serialized
        for name in [
            "password_hash",
            "secret_ciphertext",
            "token_hash",
            "code_hash",
            "provisioningUri",
        ]
    )
    assert fields_absent
    latest = records[-1]["payload"]["snapshot"]
    assert latest["factors"][0]["state"] == "ACTIVE"
    assert len(latest["codes"]) == 8
    assert all(s["revoked"] for s in latest["sessions"])


@pytest.mark.parametrize(
    "flow",
    [rotation_flow, recovery_flow],
    ids=["rotate-and-revoke", "recovery-race-reenroll"],
)
def test_security_workflows_keep_confirmation(identity, journal, flow):
    flow(identity)
    records = checked(identity[0], journal)
    operations = {r["payload"]["operation"] for r in records}
    assert (
        "security.recovery_codes.rotated" in operations
        if flow is rotation_flow
        else "security.recovery.started" in operations
    )


def test_storage_failure_rolls_back_pending_factor(identity, journal):
    engine, ctx, password, _ = identity
    directory, _ = journal
    directory.chmod(0o755)
    with pytest.raises(ApiError) as error, engine.begin() as c:
        service.start_enrollment(c, ctx, password)
    assert error.value.code == "SECURITY_JOURNAL_UNAVAILABLE"
    with engine.connect() as c:
        assert (
            c.scalar(
                text("SELECT count(*) FROM core.mfa_factor WHERE user_id=:u"),
                {"u": ctx.user_id},
            )
            == 0
        )
    directory.chmod(0o700)
    enroll(identity)
    assert checked(engine, journal)


def test_hr_password_role_disable_and_retry(company_env, journal):
    engine, company, admin, staff = company_env
    uid = next(
        u["userId"]
        for u in users(admin, company).json()["data"]
        if u["loginId"] == "hugh-staff"
    )
    secret = "Synthetic-journal-" + str(uuid4())
    directory, _ = journal
    key = str(uuid4())
    directory.chmod(0o755)
    failed = manage(
        admin, company, "/password", {"userId": uid, "password": secret}, key=key
    )
    assert failed.status_code == 503
    assert staff.get("/api/v1/hr/work/companies").status_code == 200
    directory.chmod(0o700)
    assert (
        manage(
            admin, company, "/password", {"userId": uid, "password": secret}, key=key
        ).status_code
        == 200
    )
    assert staff.get("/api/v1/hr/work/companies").status_code == 401
    count = len(records_for(journal))
    assert (
        manage(
            admin, company, "/password", {"userId": uid, "password": secret}, key=key
        ).status_code
        == 200
    )
    assert len(records_for(journal)) == count
    for operation, body in [
        ("login-id", {"loginId": "synthetic-journal-staff"}),
        ("role", {"role": "ADMIN"}),
        ("role", {"role": "STAFF"}),
        ("disable", {}),
    ]:
        assert (
            manage(admin, company, "/" + operation, {"userId": uid, **body}).status_code
            == 200
        )
    records = checked(engine, journal)
    hr = [
        r["payload"]
        for r in records
        if r["payload"]["coverage"] == "hr.users.intent.v1"
    ]
    assert {
        "hr.users.password",
        "hr.users.role",
        "hr.users.login-id",
        "hr.users.disable",
    } <= {r["operation"] for r in hr}
    assert all(str(r["workspaceId"]) == str(company["companyId"]) for r in hr)
    assert hr[-1]["snapshot"]["core"]["user"][0]["disabled"]
    assert not hr[-1]["snapshot"]["accounts"][0]["is_active"]
    safe = secret not in json.dumps(records)
    assert safe


def test_emergency_kit_replacement_keeps_confirmation(emergency_env, journal):
    kit_flow(emergency_env)
    records = checked(emergency_env[0], journal)
    assert any(
        r["payload"]["operation"].startswith("security.emergency") for r in records
    )


@pytest.mark.parametrize(
    "flow,operation",
    [(create_flow, "hr.users.create"), (company_flow, "hr.users.company-create")],
    ids=["employee-create", "company-create"],
)
def test_hr_creation_with_journal(company_env, journal, flow, operation):
    flow(company_env)
    records = checked(company_env[0], journal)
    assert any(r["payload"]["operation"] == operation for r in records)


def test_normal_logout_with_journal(company_env, journal):
    engine, _, admin, _ = company_env
    response = admin.delete(
        "/api/v1/core/sessions/current", headers={"X-CSRF-Token": admin.csrf}
    )
    assert response.status_code == 204
    assert admin.get("/api/v1/core/sessions/current").status_code == 401
    records = checked(engine, journal)
    assert records[-1]["payload"]["operation"] == "security.session.logout"
